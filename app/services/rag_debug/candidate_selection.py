from app.models.document import RagChunk
from app.services.rag_debug.scoring import is_low_information_chunk, round_score
from app.services.rag_debug.scoring_rules import (
    HEADING_PROTECTION_MIN_SCORE,
    LEXICAL_PROTECTION_MIN_SCORE,
    PROTECTED_RECALL_TOP_K,
)
from app.services.rag_debug.types import CandidateDraft, SearchProfile


def merge_candidates(
    *,
    vector_rows: list[tuple[RagChunk, str, float]],
    keyword_rows: list[tuple[RagChunk, str, float]],
    trgm_rows: list[tuple[RagChunk, str, float]],
) -> dict[int, CandidateDraft]:
    candidates: dict[int, CandidateDraft] = {}

    # 同一个 chunk 可能被多路召回命中，这里按 chunk.id 合并得分并累计召回通道。
    for chunk, document_name, score in vector_rows:
        draft = candidates.setdefault(chunk.id, CandidateDraft(chunk=chunk, document_name=document_name))
        draft.vector_score = score
        draft.recall_channels.add("vector")

    for chunk, document_name, score in keyword_rows:
        draft = candidates.setdefault(chunk.id, CandidateDraft(chunk=chunk, document_name=document_name))
        draft.keyword_score = score
        draft.recall_channels.add("keyword")

    for chunk, document_name, score in trgm_rows:
        draft = candidates.setdefault(chunk.id, CandidateDraft(chunk=chunk, document_name=document_name))
        draft.trgm_score = score
        draft.recall_channels.add("trgm")

    return candidates


def select_final_chunks(candidates: list[CandidateDraft], *, profile: SearchProfile) -> list[CandidateDraft]:
    selected: list[CandidateDraft] = []
    selected_chunk_ids: set[int] = set()
    seen_parent_ids: set[int] = set()

    def add_candidate(candidate: CandidateDraft) -> bool:
        # 统一的入选函数：保护槽和按总分补齐都走这里，保证阈值、低信息过滤、父 chunk 去重一致。
        if len(selected) >= profile.final_top_k:
            return False
        if candidate.final_score < profile.min_final_score:
            return False
        if is_low_information_chunk(candidate.chunk):
            return False
        parent_id = candidate.chunk.parent_chunk_id or candidate.chunk.id
        if candidate.chunk.id in selected_chunk_ids:
            return False
        if parent_id in seen_parent_ids:
            return False
        selected.append(candidate)
        selected_chunk_ids.add(candidate.chunk.id)
        seen_parent_ids.add(parent_id)
        return True

    # 先处理保护槽：heading 强命中和 keyword 强命中各最多保护 1 个，防止被纯 vector 高分候选全部挤掉。
    for protected_candidates in (
        top_heading_match_candidates(candidates),
        top_keyword_match_candidates(candidates),
    ):
        for candidate in protected_candidates:
            if add_candidate(candidate):
                break

    # 保护槽之后，再按 final_score 的原始排名补齐剩余名额。
    for candidate in candidates:
        add_candidate(candidate)
        if len(selected) >= profile.final_top_k:
            break

    # 返回时仍按原候选排名顺序输出，避免 Prompt/页面顺序被保护槽插入顺序打乱。
    return [candidate for candidate in candidates if candidate.chunk.id in selected_chunk_ids]


def top_keyword_match_candidates(candidates: list[CandidateDraft]) -> list[CandidateDraft]:
    # keyword 保护槽只看 keyword_score 达标的候选，再从强命中 top 3 中择优。
    strong_candidates = [
        candidate
        for candidate in candidates
        if candidate.keyword_score >= LEXICAL_PROTECTION_MIN_SCORE
    ]
    return sorted(
        strong_candidates,
        key=lambda candidate: (candidate.keyword_score, candidate.final_score),
        reverse=True,
    )[:PROTECTED_RECALL_TOP_K]


def top_heading_match_candidates(candidates: list[CandidateDraft]) -> list[CandidateDraft]:
    # heading 保护槽只看标题/章节字段命中，避免正文散词命中冒充结构化标题命中。
    strong_candidates = [
        candidate
        for candidate in candidates
        if candidate.heading_score >= HEADING_PROTECTION_MIN_SCORE
    ]
    return sorted(
        strong_candidates,
        key=lambda candidate: (candidate.heading_score, candidate.final_score),
        reverse=True,
    )[:PROTECTED_RECALL_TOP_K]


def top_k(rows: list[tuple[RagChunk, str, float]], *, top_k: int) -> list[tuple[RagChunk, str, float]]:
    if top_k <= 0:
        return []
    positive_rows = [(chunk, document_name, round_score(score)) for chunk, document_name, score in rows if score > 0]
    return sorted(positive_rows, key=lambda row: row[2], reverse=True)[:top_k]
