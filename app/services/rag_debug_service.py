import math
import re
import time
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import (
    RagChunk,
    RagDocument,
    RagDocumentVersion,
    RagEvalCase,
    RagFailureCase,
    RagQueryCandidate,
    RagQueryLog,
    RagSynonymGroup,
    RagSynonymTerm,
)
from app.schemas.rag import (
    CreateEvalCaseFromQueryLogRequest,
    CreateFailureCaseFromQueryLogRequest,
    DebugCandidateResponse,
    DebugDocumentDiagnosticsResponse,
    DebugDocumentStatusMatchResponse,
    DebugLlmResponse,
    DebugPromptResponse,
    DebugQueryRequest,
    DebugQueryResponse,
    DebugSearchProfileResponse,
    EvalCaseCreatedFrom,
    EvalCaseResponse,
    EvalCaseStatus,
    FailureCaseResponse,
    FailureSourceType,
    QueryLogDetailResponse,
)
from app.services.embedding import create_embedding_service

ANSWER_PROMPT_VERSION = "rag_qa_v1"
NO_RECALL_ANSWER = "根据当前资料无法确定。"
CJK_STOP_CHARS = set("的是了嘛吗呢啊呀么什请问和与或及在对从为")
COLLOQUIAL_QUERY_NOISE = ("告诉我", "我的", "是啥")


@dataclass
class SearchProfile:
    id: int | None
    name: str
    mode: str
    vector_top_k: int
    keyword_top_k: int
    trgm_top_k: int
    final_top_k: int
    vector_weight: float
    keyword_weight: float
    trgm_weight: float
    min_final_score: float


@dataclass
class CandidateDraft:
    chunk: RagChunk
    document_name: str
    vector_score: float = 0
    keyword_score: float = 0
    trgm_score: float = 0
    final_score: float = 0
    selected_for_prompt: bool = False
    rank: int = 0


@dataclass(frozen=True)
class NormalizedQuery:
    original_text: str
    normalized_text: str
    expanded_text: str
    applied_synonym_groups: tuple[str, ...] = ()


@dataclass(frozen=True)
class QuerySynonymGroup:
    name: str
    terms: tuple[str, ...]


def run_debug_query(db: Session, request: DebugQueryRequest) -> DebugQueryResponse:
    started_at = time.perf_counter()
    profile = _profile_from_request(request)
    chunks = _list_searchable_chunks(db)
    diagnostics = _build_document_diagnostics(db, request.question, searchable_child_chunk_count=len(chunks))
    synonym_groups = _load_active_synonym_groups(db)
    normalized_query = _normalize_query(request.question, synonym_groups=synonym_groups)
    query_embedding = _embed_query(normalized_query.expanded_text) if profile.vector_top_k > 0 else None

    vector_rows = _top_k(
        [
            (chunk, document_name, _vector_score(query_embedding, chunk.embedding))
            for chunk, document_name in chunks
            if query_embedding is not None and _has_embedding(chunk.embedding)
        ],
        top_k=profile.vector_top_k,
    )
    keyword_rows = _top_k(
        [
            (
                chunk,
                document_name,
                _keyword_score(
                    request.question,
                    chunk.search_text or chunk.content_with_context or chunk.content,
                    normalized_query=normalized_query,
                ),
            )
            for chunk, document_name in chunks
        ],
        top_k=profile.keyword_top_k,
    )
    trgm_rows = _top_k(
        [
            (
                chunk,
                document_name,
                _trgm_score(
                    request.question,
                    chunk.search_text or chunk.content_with_context or chunk.content,
                    normalized_query=normalized_query,
                ),
            )
            for chunk, document_name in chunks
        ],
        top_k=profile.trgm_top_k,
    )

    candidates = _merge_candidates(vector_rows=vector_rows, keyword_rows=keyword_rows, trgm_rows=trgm_rows)
    for candidate in candidates.values():
        candidate.final_score = _candidate_final_score(candidate, profile)

    ranked_candidates = sorted(candidates.values(), key=lambda candidate: candidate.final_score, reverse=True)
    selected_candidates = _select_final_chunks(ranked_candidates, profile=profile)
    selected_ids = {candidate.chunk.id for candidate in selected_candidates}
    for index, candidate in enumerate(ranked_candidates, start=1):
        candidate.rank = index
        candidate.selected_for_prompt = candidate.chunk.id in selected_ids

    prompt = _build_prompt(request.question, selected_candidates) if request.use_llm and selected_candidates else None
    llm = _build_llm_response(use_llm=request.use_llm, has_selected_chunks=bool(selected_candidates))
    total_latency_ms = _elapsed_ms(started_at)
    query_log = _persist_query_log(
        db,
        request=request,
        profile=profile,
        candidates=ranked_candidates,
        prompt=prompt,
        llm=llm,
        total_latency_ms=total_latency_ms,
    )

    return DebugQueryResponse(
        query_log_id=query_log.id,
        question=request.question,
        search_profile=_profile_response(profile),
        candidates=[_candidate_response(candidate) for candidate in ranked_candidates],
        selected_chunks=[_candidate_response(candidate) for candidate in selected_candidates],
        prompt=prompt,
        diagnostics=diagnostics,
        llm=llm,
    )


def get_query_log_detail(db: Session, query_log_id: int) -> QueryLogDetailResponse | None:
    query_log = db.get(RagQueryLog, query_log_id)
    if query_log is None:
        return None

    candidate_rows = list(
        db.scalars(
            select(RagQueryCandidate)
            .where(RagQueryCandidate.query_log_id == query_log_id)
            .order_by(RagQueryCandidate.rank.asc(), RagQueryCandidate.id.asc())
        )
    )
    candidates = [_candidate_response_from_log(row) for row in candidate_rows]
    selected_chunks = [candidate for candidate in candidates if candidate.selected_for_prompt]
    prompt = (
        DebugPromptResponse(version=query_log.answer_prompt_version or ANSWER_PROMPT_VERSION, text=query_log.answer_prompt_text)
        if query_log.answer_prompt_text
        else None
    )
    llm = DebugLlmResponse(
        used=bool(query_log.use_llm and query_log.answer),
        model=query_log.llm_model,
        latency_ms=query_log.llm_latency_ms,
        answer=query_log.answer,
        error=query_log.llm_error,
    )
    diagnostics = _build_document_diagnostics(db, query_log.question)

    return QueryLogDetailResponse(
        id=query_log.id,
        question=query_log.question,
        search_mode=query_log.search_mode,
        use_llm=query_log.use_llm,
        created_at=query_log.created_at,
        search_profile=DebugSearchProfileResponse(**(query_log.search_profile_snapshot or {})),
        model_config_snapshot=query_log.model_config_snapshot,
        search_latency_ms=query_log.search_latency_ms,
        llm_latency_ms=query_log.llm_latency_ms,
        total_latency_ms=query_log.total_latency_ms,
        candidates=candidates,
        selected_chunks=selected_chunks,
        prompt=prompt,
        diagnostics=diagnostics,
        llm=llm,
    )


def create_failure_case_from_query_log(
    db: Session,
    query_log_id: int,
    request: CreateFailureCaseFromQueryLogRequest,
) -> FailureCaseResponse | None:
    query_log = db.get(RagQueryLog, query_log_id)
    if query_log is None:
        return None

    now = datetime.utcnow()
    failure_case = RagFailureCase(
        query_log_id=query_log.id,
        source_type=FailureSourceType.MANUAL_DEBUG,
        source_ref_id=None,
        source_reason=request.source_reason or request.primary_failure_type,
        source_payload=_query_log_source_payload(db, query_log),
        primary_failure_type=request.primary_failure_type,
        analysis_note=request.analysis_note,
        fix_plan=request.fix_plan,
        status=request.status,
        priority=request.priority,
        fixed_at=now if request.status == "FIXED" else None,
    )
    db.add(failure_case)
    db.commit()
    db.refresh(failure_case)
    return FailureCaseResponse.model_validate(failure_case)


def create_eval_case_from_query_log(
    db: Session,
    query_log_id: int,
    request: CreateEvalCaseFromQueryLogRequest,
) -> EvalCaseResponse | None:
    query_log = db.get(RagQueryLog, query_log_id)
    if query_log is None:
        return None

    now = datetime.utcnow()
    eval_case = RagEvalCase(
        question=request.question or query_log.question,
        expected_answer=request.expected_answer,
        case_type=request.case_type,
        status=request.status,
        priority=request.priority,
        created_from=EvalCaseCreatedFrom.QUERY_LOG,
        source_ref_id=query_log.id,
        source_payload=_query_log_source_payload(db, query_log),
        review_note=request.review_note,
        reviewed_at=now if request.status in {EvalCaseStatus.ACTIVE, EvalCaseStatus.REJECTED} else None,
        activated_at=now if request.status == EvalCaseStatus.ACTIVE else None,
    )
    db.add(eval_case)
    db.commit()
    db.refresh(eval_case)
    return EvalCaseResponse.model_validate(eval_case)


def _profile_from_request(request: DebugQueryRequest) -> SearchProfile:
    settings = get_settings()
    vector_top_k = request.vector_top_k
    vector_weight = request.vector_weight
    if settings.embedding_provider == "fake" and not {"vector_top_k", "vector_weight"} & request.model_fields_set:
        vector_top_k = 0
        vector_weight = 0

    return SearchProfile(
        id=request.search_profile_id,
        name="默认混合检索" if vector_top_k > 0 else "本地关键词检索",
        mode="HYBRID" if vector_top_k > 0 else "LEXICAL",
        vector_top_k=vector_top_k,
        keyword_top_k=request.keyword_top_k,
        trgm_top_k=request.trgm_top_k,
        final_top_k=request.final_top_k,
        vector_weight=vector_weight,
        keyword_weight=request.keyword_weight,
        trgm_weight=request.trgm_weight,
        min_final_score=request.min_final_score,
    )


def _list_searchable_chunks(db: Session) -> list[tuple[RagChunk, str]]:
    rows = db.execute(
        select(RagChunk, RagDocument.name)
        .join(RagDocument, RagDocument.id == RagChunk.document_id)
        .where(
            RagDocument.status == "ACTIVE",
            RagDocument.current_version_id == RagChunk.document_version_id,
            RagChunk.chunk_type == "CHILD",
        )
    )
    return [(chunk, document_name) for chunk, document_name in rows]


def _build_document_diagnostics(
    db: Session,
    question: str,
    *,
    searchable_child_chunk_count: int | None = None,
) -> DebugDocumentDiagnosticsResponse:
    active_document_count = db.scalar(select(func.count()).select_from(RagDocument).where(RagDocument.status == "ACTIVE")) or 0
    if searchable_child_chunk_count is None:
        searchable_child_chunk_count = (
            db.scalar(
                select(func.count())
                .select_from(RagChunk)
                .join(RagDocument, RagDocument.id == RagChunk.document_id)
                .where(
                    RagDocument.status == "ACTIVE",
                    RagDocument.current_version_id == RagChunk.document_version_id,
                    RagChunk.chunk_type == "CHILD",
                )
            )
            or 0
        )

    excluded_rows = db.execute(
        select(RagDocument, RagDocumentVersion)
        .outerjoin(RagDocumentVersion, RagDocumentVersion.id == RagDocument.current_version_id)
        .where(
            or_(
                RagDocument.status != "ACTIVE",
                RagDocument.current_version_id.is_(None),
                RagDocumentVersion.id.is_(None),
                RagDocumentVersion.status != "COMPLETED",
            )
        )
        .order_by(RagDocument.updated_at.desc(), RagDocument.id.desc())
        .limit(80)
    )

    related_documents: list[DebugDocumentStatusMatchResponse] = []
    for document, version in excluded_rows:
        chunks = _list_document_current_child_chunks(db, document)
        match_reason = _diagnostic_match_reason(question, document, chunks)
        if not match_reason:
            continue
        related_documents.append(
            DebugDocumentStatusMatchResponse(
                document_id=document.id,
                name=document.name,
                status=document.status,
                current_version_id=document.current_version_id,
                version_status=version.status if version else None,
                chunk_count=version.chunk_count if version else None,
                match_reason=match_reason,
            )
        )

    warnings: list[str] = []
    if searchable_child_chunk_count == 0:
        warnings.append("当前没有可检索 CHILD chunk，请先确认文档状态、当前版本和入库结果。")
    if related_documents:
        warnings.append(
            f"发现 {len(related_documents)} 个相关文档未参与检索，可能是状态非 ACTIVE 或当前版本不可检索。"
        )

    return DebugDocumentDiagnosticsResponse(
        active_document_count=active_document_count,
        searchable_child_chunk_count=searchable_child_chunk_count,
        inactive_related_documents=related_documents[:10],
        warnings=warnings,
    )


def _list_document_current_child_chunks(db: Session, document: RagDocument) -> list[RagChunk]:
    if document.current_version_id is None:
        return []
    return list(
        db.scalars(
            select(RagChunk)
            .where(
                RagChunk.document_id == document.id,
                RagChunk.document_version_id == document.current_version_id,
                RagChunk.chunk_type == "CHILD",
            )
            .order_by(RagChunk.chunk_index.asc(), RagChunk.child_index.asc())
            .limit(60)
        )
    )


def _diagnostic_match_reason(question: str, document: RagDocument, chunks: list[RagChunk]) -> str | None:
    if not question.strip():
        return None
    text_parts = [document.name]
    for chunk in chunks:
        text_parts.extend(
            part
            for part in [chunk.heading_path, chunk.section_title, chunk.search_text, chunk.content_with_context, chunk.content]
            if part
        )
    haystack = "\n".join(text_parts).lower()
    coverage = _character_coverage_score(question, haystack)
    if coverage < 0.35 and _keyword_score(question, haystack) < 0.35:
        return None
    return "文档名/标题/内容与问题关键词匹配"


def _embed_query(question: str) -> list[float]:
    settings = get_settings()
    return create_embedding_service(settings).embed_query(question)


def _merge_candidates(
    *,
    vector_rows: list[tuple[RagChunk, str, float]],
    keyword_rows: list[tuple[RagChunk, str, float]],
    trgm_rows: list[tuple[RagChunk, str, float]],
) -> dict[int, CandidateDraft]:
    candidates: dict[int, CandidateDraft] = {}

    for chunk, document_name, score in vector_rows:
        draft = candidates.setdefault(chunk.id, CandidateDraft(chunk=chunk, document_name=document_name))
        draft.vector_score = score

    for chunk, document_name, score in keyword_rows:
        draft = candidates.setdefault(chunk.id, CandidateDraft(chunk=chunk, document_name=document_name))
        draft.keyword_score = score

    for chunk, document_name, score in trgm_rows:
        draft = candidates.setdefault(chunk.id, CandidateDraft(chunk=chunk, document_name=document_name))
        draft.trgm_score = score

    return candidates


def _select_final_chunks(candidates: list[CandidateDraft], *, profile: SearchProfile) -> list[CandidateDraft]:
    selected: list[CandidateDraft] = []
    seen_parent_ids: set[int] = set()

    for candidate in candidates:
        if candidate.final_score < profile.min_final_score:
            continue
        if _is_low_information_chunk(candidate.chunk):
            continue
        parent_id = candidate.chunk.parent_chunk_id or candidate.chunk.id
        if parent_id in seen_parent_ids:
            continue
        selected.append(candidate)
        seen_parent_ids.add(parent_id)
        if len(selected) >= profile.final_top_k:
            break

    return selected


def _top_k(rows: list[tuple[RagChunk, str, float]], *, top_k: int) -> list[tuple[RagChunk, str, float]]:
    if top_k <= 0:
        return []
    positive_rows = [(chunk, document_name, _round_score(score)) for chunk, document_name, score in rows if score > 0]
    return sorted(positive_rows, key=lambda row: row[2], reverse=True)[:top_k]


def _has_embedding(value) -> bool:
    return value is not None and len(value) > 0


def _vector_score(query_embedding: list[float] | None, chunk_embedding) -> float:
    if not query_embedding or not _has_embedding(chunk_embedding):
        return 0
    chunk_embedding = list(chunk_embedding)
    length = min(len(query_embedding), len(chunk_embedding))
    if length == 0:
        return 0
    query = query_embedding[:length]
    chunk = chunk_embedding[:length]
    dot = sum(left * right for left, right in zip(query, chunk, strict=True))
    query_norm = math.sqrt(sum(value * value for value in query))
    chunk_norm = math.sqrt(sum(value * value for value in chunk))
    if query_norm == 0 or chunk_norm == 0:
        return 0
    cosine_similarity = dot / (query_norm * chunk_norm)
    return _round_score(_clamp(cosine_similarity))


def _keyword_score(question: str, text: str, *, normalized_query: NormalizedQuery | None = None) -> float:
    normalized_query = normalized_query or _normalize_query(question)
    haystack = text.lower()
    if not normalized_query.normalized_text or not haystack:
        return 0
    return max(
        _keyword_score_for_query(normalized_query.normalized_text, haystack),
        _keyword_score_for_query(normalized_query.expanded_text, haystack),
    )


def _keyword_score_for_query(query: str, haystack: str) -> float:
    query = query.strip().lower()
    if not query:
        return 0
    terms = _terms(query)
    if not terms:
        return 0
    matched = sum(1 for term in terms if term in haystack)
    coverage = matched / len(terms)
    if query in haystack:
        coverage = 1
    return _round_score(max(_clamp(coverage), _character_coverage_score_for_query(query, haystack)))


def _trgm_score(question: str, text: str, *, normalized_query: NormalizedQuery | None = None) -> float:
    normalized_query = normalized_query or _normalize_query(question)
    haystack = text.lower()
    if not normalized_query.normalized_text or not haystack:
        return 0
    return max(
        _trgm_score_for_query(normalized_query.normalized_text, haystack),
        _trgm_score_for_query(normalized_query.expanded_text, haystack),
    )


def _trgm_score_for_query(query: str, haystack: str) -> float:
    query = query.strip().lower()
    if not query:
        return 0
    if query in haystack:
        return 1
    return _round_score(_clamp(SequenceMatcher(None, query, haystack).ratio()))


def _terms(value: str) -> list[str]:
    ascii_terms = re.findall(r"[a-z0-9]+", value.lower())
    cjk_terms = [
        char
        for char in re.findall(r"[\u4e00-\u9fff]", value)
        if char not in CJK_STOP_CHARS
    ]
    return ascii_terms + cjk_terms


def _normalize_query(value: str, synonym_groups: list[QuerySynonymGroup] | None = None) -> NormalizedQuery:
    normalized = value.strip()
    for noise in COLLOQUIAL_QUERY_NOISE:
        normalized = normalized.replace(noise, "")
    normalized = re.sub(r"\s+", " ", normalized).strip()

    expanded_terms: list[str] = []
    applied_groups: list[str] = []
    for group in synonym_groups or []:
        if not _query_matches_synonym_group(normalized, group):
            continue
        applied_groups.append(group.name)
        expanded_terms.extend(term for term in group.terms if not _contains_term(normalized, term))

    expanded = " ".join(_dedupe_terms([part for part in [normalized, *expanded_terms] if part])).strip()
    return NormalizedQuery(
        original_text=value,
        normalized_text=normalized,
        expanded_text=expanded,
        applied_synonym_groups=tuple(_dedupe_terms(applied_groups)),
    )


def _load_active_synonym_groups(db: Session) -> list[QuerySynonymGroup]:
    rows = db.execute(
        select(RagSynonymGroup.name, RagSynonymTerm.term)
        .join(RagSynonymTerm, RagSynonymTerm.group_id == RagSynonymGroup.id)
        .where(RagSynonymGroup.status == "ACTIVE", RagSynonymTerm.status == "ACTIVE")
        .order_by(RagSynonymGroup.id.asc(), RagSynonymTerm.term_type.asc(), RagSynonymTerm.id.asc())
    )
    terms_by_group: dict[str, list[str]] = {}
    for group_name, term in rows:
        terms_by_group.setdefault(group_name, []).append(term)
    return [
        QuerySynonymGroup(name=group_name, terms=tuple(_dedupe_terms(terms)))
        for group_name, terms in terms_by_group.items()
        if terms
    ]


def _query_matches_synonym_group(query: str, group: QuerySynonymGroup) -> bool:
    return any(_contains_term(query, term) for term in group.terms)


def _contains_term(value: str, term: str) -> bool:
    if not term:
        return False
    return term.lower() in value.lower()


def _dedupe_terms(values: list[str] | tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized_value = value.strip()
        key = normalized_value.lower()
        if not normalized_value or key in seen:
            continue
        seen.add(key)
        result.append(normalized_value)
    return result


def _character_coverage_score(question: str, text: str) -> float:
    normalized_query = _normalize_query(question)
    return max(
        _character_coverage_score_for_query(normalized_query.normalized_text, text),
        _character_coverage_score_for_query(normalized_query.expanded_text, text),
    )


def _character_coverage_score_for_query(query: str, text: str) -> float:
    ascii_terms = re.findall(r"[a-z0-9]+", query.lower())
    cjk_chars = {
        char
        for char in re.findall(r"[\u4e00-\u9fff]", query)
        if char not in CJK_STOP_CHARS
    }
    total_units = len(ascii_terms) + len(cjk_chars)
    if total_units == 0:
        return 0

    matched_ascii = sum(1 for term in ascii_terms if term in text)
    matched_cjk = sum(1 for char in cjk_chars if char in text)
    return _round_score((matched_ascii + matched_cjk) / total_units)


def _candidate_final_score(candidate: CandidateDraft, profile: SearchProfile) -> float:
    weighted_scores = (
        (profile.vector_weight, candidate.vector_score),
        (profile.keyword_weight, candidate.keyword_score),
        (profile.trgm_weight, candidate.trgm_score),
    )
    active_scores = [(weight, score) for weight, score in weighted_scores if weight > 0 and score > 0]
    active_weight = sum(weight for weight, _ in active_scores)
    if active_weight == 0:
        return 0
    return _round_score(sum(weight * score for weight, score in active_scores) / active_weight)


def _is_low_information_chunk(chunk: RagChunk) -> bool:
    content = (chunk.content or "").strip().replace("\\", "")
    if not content:
        return True
    if re.fullmatch(r"[\s`\-_*|:]+", content):
        return True
    return content.lower() in {"```", "```txt", "```text", "```plain text", "```python", "```json"}


def _build_prompt(question: str, selected_candidates: list[CandidateDraft]) -> DebugPromptResponse:
    context_blocks = []
    for index, candidate in enumerate(selected_candidates, start=1):
        chunk = candidate.chunk
        section = chunk.heading_path or chunk.section_title or "未分章节"
        content = chunk.content_with_context or chunk.content
        context_blocks.append(
            f"[片段{index}] 文档：{candidate.document_name}\n章节：{section}\n内容：{content}"
        )

    text = (
        "你是一个知识库问答助手。请只根据给定资料回答问题；"
        "如果资料不足，请回答“根据当前资料无法确定”。\n\n"
        f"问题：{question}\n\n"
        "资料：\n"
        + "\n\n".join(context_blocks)
    )
    return DebugPromptResponse(version=ANSWER_PROMPT_VERSION, text=text)


def _build_llm_response(*, use_llm: bool, has_selected_chunks: bool) -> DebugLlmResponse:
    if not use_llm:
        return DebugLlmResponse(used=False, answer=None)
    if not has_selected_chunks:
        return DebugLlmResponse(used=False, answer=NO_RECALL_ANSWER)
    return DebugLlmResponse(used=False, error="LLM provider is not configured")


def _candidate_response(candidate: CandidateDraft) -> DebugCandidateResponse:
    chunk = candidate.chunk
    return DebugCandidateResponse(
        rank=candidate.rank,
        chunk_id=chunk.id,
        document_id=chunk.document_id,
        document_version_id=chunk.document_version_id,
        document_name=candidate.document_name,
        section_title=chunk.section_title,
        heading_path=chunk.heading_path,
        parent_chunk_id=chunk.parent_chunk_id,
        chunk_index=chunk.chunk_index,
        child_index=chunk.child_index,
        start_char=chunk.start_char,
        end_char=chunk.end_char,
        page_number=None,
        vector_score=candidate.vector_score,
        keyword_score=candidate.keyword_score,
        trgm_score=candidate.trgm_score,
        final_score=candidate.final_score,
        selected_for_prompt=candidate.selected_for_prompt,
        content_preview=chunk.content[:160],
        content=chunk.content,
        content_with_context=chunk.content_with_context,
    )


def _profile_response(profile: SearchProfile) -> DebugSearchProfileResponse:
    return DebugSearchProfileResponse(**profile.__dict__)


def _persist_query_log(
    db: Session,
    *,
    request: DebugQueryRequest,
    profile: SearchProfile,
    candidates: list[CandidateDraft],
    prompt: DebugPromptResponse | None,
    llm: DebugLlmResponse,
    total_latency_ms: int,
) -> RagQueryLog:
    settings = get_settings()
    scores = [candidate.final_score for candidate in candidates]
    search_profile = _profile_response(profile)
    query_log = RagQueryLog(
        question=request.question,
        search_mode=profile.mode,
        use_llm=request.use_llm,
        search_profile_id=profile.id,
        search_profile_snapshot=search_profile.model_dump(),
        model_config_snapshot={
            "embedding": {
                "provider": settings.embedding_provider,
                "model": settings.embedding_model,
                "dimension": settings.embedding_dimension,
            },
            "llm": {
                "provider": settings.llm_provider,
                "model": settings.llm_model if request.use_llm else None,
            },
        },
        answer_prompt_version=prompt.version if prompt else None,
        top_k=max(profile.vector_top_k, profile.keyword_top_k, profile.trgm_top_k),
        final_top_k=profile.final_top_k,
        embedding_model=settings.embedding_model if profile.vector_top_k > 0 else None,
        llm_model=settings.llm_model if request.use_llm else None,
        answer_prompt_text=prompt.text if prompt else None,
        answer=llm.answer,
        max_score=max(scores) if scores else None,
        min_score=min(scores) if scores else None,
        search_latency_ms=total_latency_ms,
        llm_latency_ms=llm.latency_ms,
        total_latency_ms=total_latency_ms,
        llm_error=llm.error,
    )
    db.add(query_log)
    db.flush()

    for candidate in candidates:
        chunk = candidate.chunk
        db.add(
            RagQueryCandidate(
                query_log_id=query_log.id,
                chunk_id=chunk.id,
                parent_chunk_id=chunk.parent_chunk_id,
                document_id=chunk.document_id,
                document_version_id=chunk.document_version_id,
                document_name=candidate.document_name,
                section_title=chunk.section_title,
                heading_path=chunk.heading_path,
                rank=candidate.rank,
                chunk_index=chunk.chunk_index,
                child_index=chunk.child_index,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                vector_score=candidate.vector_score,
                keyword_score=candidate.keyword_score,
                trgm_score=candidate.trgm_score,
                final_score=candidate.final_score,
                selected_for_prompt=candidate.selected_for_prompt,
                content_preview=chunk.content[:160],
                content_snapshot=chunk.content,
                content_with_context_snapshot=chunk.content_with_context,
            )
        )

    db.commit()
    db.refresh(query_log)
    return query_log


def _candidate_response_from_log(candidate: RagQueryCandidate) -> DebugCandidateResponse:
    return DebugCandidateResponse(
        rank=candidate.rank,
        chunk_id=candidate.chunk_id,
        document_id=candidate.document_id,
        document_version_id=candidate.document_version_id,
        document_name=candidate.document_name,
        section_title=candidate.section_title,
        heading_path=candidate.heading_path,
        parent_chunk_id=candidate.parent_chunk_id,
        chunk_index=candidate.chunk_index,
        child_index=candidate.child_index,
        start_char=candidate.start_char,
        end_char=candidate.end_char,
        page_number=None,
        vector_score=candidate.vector_score,
        keyword_score=candidate.keyword_score,
        trgm_score=candidate.trgm_score,
        final_score=candidate.final_score,
        selected_for_prompt=candidate.selected_for_prompt,
        content_preview=candidate.content_preview,
        content=candidate.content_snapshot,
        content_with_context=candidate.content_with_context_snapshot,
    )


def _query_log_source_payload(db: Session, query_log: RagQueryLog) -> dict:
    candidates = list(
        db.scalars(
            select(RagQueryCandidate)
            .where(RagQueryCandidate.query_log_id == query_log.id)
            .order_by(RagQueryCandidate.rank.asc(), RagQueryCandidate.id.asc())
        )
    )
    selected_candidates = [candidate for candidate in candidates if candidate.selected_for_prompt]
    return {
        "query_log_id": query_log.id,
        "question": query_log.question,
        "search_mode": query_log.search_mode,
        "use_llm": query_log.use_llm,
        "search_profile": query_log.search_profile_snapshot,
        "model_config": query_log.model_config_snapshot,
        "candidate_count": len(candidates),
        "diagnostics": _build_document_diagnostics(db, query_log.question).model_dump(),
        "selected_chunks": [
            {
                "rank": candidate.rank,
                "chunk_id": candidate.chunk_id,
                "document_id": candidate.document_id,
                "document_name": candidate.document_name,
                "section_title": candidate.section_title,
                "heading_path": candidate.heading_path,
                "start_char": candidate.start_char,
                "end_char": candidate.end_char,
                "final_score": candidate.final_score,
                "content_preview": candidate.content_preview,
            }
            for candidate in selected_candidates
        ],
        "llm_error": query_log.llm_error,
    }


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((time.perf_counter() - started_at) * 1000))


def _clamp(value: float) -> float:
    return max(0, min(1, value))


def _round_score(value: float) -> float:
    return round(_clamp(value), 6)
