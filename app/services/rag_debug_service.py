import time

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.rag import DebugQueryRequest, DebugQueryResponse
from app.services.embedding import create_embedding_service
from app.services.rag_debug.candidate_selection import (
    merge_candidates,
    select_final_chunks,
    top_heading_match_candidates,
    top_k,
    top_keyword_match_candidates,
)
from app.services.rag_debug.diagnostics import (
    build_document_diagnostics,
    diagnostic_match_reason,
    filter_candidate_chunks,
    list_document_current_child_chunks,
    list_searchable_chunks,
)
from app.services.rag_debug.prompting import (
    ANSWER_PROMPT_VERSION,
    NO_RECALL_ANSWER,
    build_llm_response,
    build_prompt,
)
from app.services.rag_debug.query_logs import (
    candidate_response,
    candidate_response_from_log,
    create_eval_case_from_query_log,
    create_failure_case_from_query_log,
    get_query_log_detail,
    persist_query_log,
    profile_response,
    query_log_source_payload,
)
from app.services.rag_debug.query_normalization import (
    CJK_STOP_CHARS,
    COLLOQUIAL_QUERY_NOISE,
    ascii_match_terms,
    ascii_match_token_set,
    contains_term,
    dedupe_terms,
    is_ascii_term,
    load_active_synonym_groups,
    normalize_query_text,
    query_exact_match_score,
    query_matches_synonym_group,
    query_terms,
)
from app.services.rag_debug.scoring import (
    _character_coverage_score_for_query,
    _clamp,
    _is_directory_like_chunk,
    _is_list_like_line,
    _keyword_score_for_query,
    _looks_like_markdown_table,
    _max_keyword_score,
    _max_trgm_score,
    _phrase_match_score,
    _query_phrases,
    _query_variants,
    _synonym_intent_score,
    _topic_haystack,
    _topic_query_text,
    _trgm_score_for_query,
    apply_topic_gate,
    candidate_final_score,
    character_coverage_score,
    field_aware_heading_score,
    field_aware_keyword_score,
    field_aware_trgm_score,
    has_embedding,
    is_low_information_chunk,
    keyword_score,
    quality_multiplier,
    round_score,
    trgm_score,
    vector_score,
)
from app.services.rag_debug.scoring_rules import (
    HEADING_PROTECTION_MIN_SCORE,
    INTENT_GATE_MIN_SCORE,
    LEXICAL_PROTECTION_MIN_SCORE,
    PROTECTED_RECALL_TOP_K,
    TOPIC_GATE_MIN_SCORE,
    TOPICLESS_SYNONYM_SCORE_CAP,
)
from app.services.rag_debug.types import CandidateDraft, NormalizedQuery, QuerySynonymGroup, SearchProfile

# 兼容旧调用路径：API 层仍从本模块导入入口函数，历史测试和调试脚本也可能导入这些私有名称。
_merge_candidates = merge_candidates
_select_final_chunks = select_final_chunks
_top_heading_match_candidates = top_heading_match_candidates
_top_k = top_k
_top_keyword_match_candidates = top_keyword_match_candidates
_build_document_diagnostics = build_document_diagnostics
_diagnostic_match_reason = diagnostic_match_reason
_filter_candidate_chunks = filter_candidate_chunks
_list_document_current_child_chunks = list_document_current_child_chunks
_list_searchable_chunks = list_searchable_chunks
_build_llm_response = build_llm_response
_build_prompt = build_prompt
_candidate_response = candidate_response
_candidate_response_from_log = candidate_response_from_log
_persist_query_log = persist_query_log
_profile_response = profile_response
_query_log_source_payload = query_log_source_payload
_ascii_match_terms = ascii_match_terms
_ascii_match_token_set = ascii_match_token_set
_contains_term = contains_term
_dedupe_terms = dedupe_terms
_is_ascii_term = is_ascii_term
_load_active_synonym_groups = load_active_synonym_groups
_normalize_query = normalize_query_text
_query_exact_match_score = query_exact_match_score
_query_matches_synonym_group = query_matches_synonym_group
_terms = query_terms
_apply_topic_gate = apply_topic_gate
_candidate_final_score = candidate_final_score
_character_coverage_score = character_coverage_score
_field_aware_heading_score = field_aware_heading_score
_field_aware_keyword_score = field_aware_keyword_score
_field_aware_trgm_score = field_aware_trgm_score
_has_embedding = has_embedding
_is_low_information_chunk = is_low_information_chunk
_keyword_score = keyword_score
_quality_multiplier = quality_multiplier
_round_score = round_score
_trgm_score = trgm_score
_vector_score = vector_score


def run_debug_query(db: Session, request: DebugQueryRequest) -> DebugQueryResponse:
    # 调试查询的业务运行函数：归一化查询、召回候选、打分、选择 Prompt 片段并记录 query log。
    started_at = time.perf_counter()
    profile = _profile_from_request(request)
    # all_chunks 保留完整可检索 CHILD 数量给文档状态诊断使用。
    all_chunks = list_searchable_chunks(db)
    # chunks 是实际参与候选召回的集合，先过滤掉 ---、代码围栏等低信息 chunk。
    chunks = filter_candidate_chunks(all_chunks)
    diagnostics = build_document_diagnostics(db, request.question, searchable_child_chunk_count=len(all_chunks))
    # 加载同义词词组并扩展查询。
    synonym_groups = load_active_synonym_groups(db)
    normalized_query = normalize_query_text(request.question, synonym_groups=synonym_groups)
    # 调取向量模型获取问题的向量数据。
    query_embedding = _embed_query(normalized_query.expanded_text) if profile.vector_top_k > 0 else None

    # 计算向量相似度并排序；这里使用过滤后的 chunks，低信息 chunk 不再进入候选池。
    vector_rows = top_k(
        [
            (chunk, document_name, vector_score(query_embedding, chunk.embedding))
            for chunk, document_name in chunks
            if query_embedding is not None and has_embedding(chunk.embedding)
        ],
        top_k=profile.vector_top_k,
    )
    keyword_rows = top_k(
        [
            (
                chunk,
                document_name,
                field_aware_keyword_score(
                    request.question,
                    chunk,
                    document_name,
                    normalized_query=normalized_query,
                ),
            )
            for chunk, document_name in chunks
        ],
        top_k=profile.keyword_top_k,
    )
    trgm_rows = top_k(
        [
            (
                chunk,
                document_name,
                field_aware_trgm_score(
                    request.question,
                    chunk,
                    document_name,
                    normalized_query=normalized_query,
                ),
            )
            for chunk, document_name in chunks
        ],
        top_k=profile.trgm_top_k,
    )

    candidates = merge_candidates(vector_rows=vector_rows, keyword_rows=keyword_rows, trgm_rows=trgm_rows)
    for candidate in candidates.values():
        # heading_score 单独计算结构化标题命中，不直接改变总分，只服务于后续保护槽选择。
        candidate.heading_score = field_aware_heading_score(
            request.question,
            candidate.chunk,
            candidate.document_name,
            normalized_query=normalized_query,
        )
        # final_score 仍只由当前 profile 的 vector/keyword/trgm 权重决定，保护槽不会改写分数。
        candidate.final_score = candidate_final_score(candidate, profile)

    ranked_candidates = sorted(candidates.values(), key=lambda candidate: candidate.final_score, reverse=True)
    selected_candidates = select_final_chunks(ranked_candidates, profile=profile)
    selected_ids = {candidate.chunk.id for candidate in selected_candidates}
    for index, candidate in enumerate(ranked_candidates, start=1):
        candidate.rank = index
        candidate.selected_for_prompt = candidate.chunk.id in selected_ids

    prompt = build_prompt(request.question, selected_candidates) if request.use_llm and selected_candidates else None
    llm = build_llm_response(use_llm=request.use_llm, has_selected_chunks=bool(selected_candidates))
    total_latency_ms = _elapsed_ms(started_at)
    query_log = persist_query_log(
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
        search_profile=profile_response(profile),
        candidates=[candidate_response(candidate) for candidate in ranked_candidates],
        selected_chunks=[candidate_response(candidate) for candidate in selected_candidates],
        prompt=prompt,
        diagnostics=diagnostics,
        llm=llm,
    )


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


def _embed_query(question: str) -> list[float]:
    settings = get_settings()
    return create_embedding_service(settings).embed_query(question)


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((time.perf_counter() - started_at) * 1000))
