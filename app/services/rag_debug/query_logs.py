from dataclasses import asdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import RagEvalCase, RagFailureCase, RagQueryCandidate, RagQueryLog
from app.schemas.rag import (
    CreateEvalCaseFromQueryLogRequest,
    CreateFailureCaseFromQueryLogRequest,
    DebugCandidateResponse,
    DebugLlmResponse,
    DebugPromptResponse,
    DebugSearchProfileResponse,
    EvalCaseCreatedFrom,
    EvalCaseResponse,
    EvalCaseStatus,
    FailureCaseResponse,
    FailureSourceType,
    QueryLogDetailResponse,
)
from app.services.rag_debug.diagnostics import build_document_diagnostics
from app.services.rag_debug.prompting import ANSWER_PROMPT_VERSION
from app.services.rag_debug.types import CandidateDraft, SearchProfile


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
    candidates = [candidate_response_from_log(row) for row in candidate_rows]
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
    diagnostics = build_document_diagnostics(db, query_log.question)

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
        source_payload=query_log_source_payload(db, query_log),
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
        source_payload=query_log_source_payload(db, query_log),
        review_note=request.review_note,
        reviewed_at=now if request.status in {EvalCaseStatus.ACTIVE, EvalCaseStatus.REJECTED} else None,
        activated_at=now if request.status == EvalCaseStatus.ACTIVE else None,
    )
    db.add(eval_case)
    db.commit()
    db.refresh(eval_case)
    return EvalCaseResponse.model_validate(eval_case)


def candidate_response(candidate: CandidateDraft) -> DebugCandidateResponse:
    # 将内存候选转换成 API 响应对象，同时保留完整 chunk 内容用于调试面板。
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


def profile_response(profile: SearchProfile) -> DebugSearchProfileResponse:
    return DebugSearchProfileResponse(**asdict(profile))


def persist_query_log(
    db: Session,
    *,
    request,
    profile: SearchProfile,
    candidates: list[CandidateDraft],
    prompt: DebugPromptResponse | None,
    llm: DebugLlmResponse,
    total_latency_ms: int,
) -> RagQueryLog:
    settings = get_settings()
    scores = [candidate.final_score for candidate in candidates]
    search_profile = profile_response(profile)
    # query log 持久化检索参数、模型配置、候选快照和 Prompt，便于后续复盘失败样本。
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


def candidate_response_from_log(candidate: RagQueryCandidate) -> DebugCandidateResponse:
    # 从 query log 候选快照恢复响应对象，不依赖当前 chunk 内容是否已变化。
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


def query_log_source_payload(db: Session, query_log: RagQueryLog) -> dict:
    # failure/eval case 使用同一份 source payload，确保样本能追溯到当次调试上下文。
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
        "diagnostics": build_document_diagnostics(db, query_log.question).model_dump(),
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
