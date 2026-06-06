from __future__ import annotations

from dataclasses import dataclass
import json
import time

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthUser
from app.core.config import Settings, get_settings
from app.models.document import RagChunk, RagQueryCandidate, RagQueryFeedback, RagQueryLog
from app.schemas.rag import (
    DebugQueryRequest,
    SearchFeedbackRequest,
    SearchFeedbackResponse,
    SearchRequest,
    SearchResponse,
    SearchResultAnswerStatus,
    SearchResultResponse,
    SearchStatus,
)
from app.services.rag_debug.prompting import NO_RECALL_ANSWER
from app.services.rag_debug_service import run_debug_query

RESULT_PROMPT_VERSION = "rag_search_results_v1"
SEARCH_RESULT_TOP_K = 5
CONTEXT_WINDOW_CHARS = 400
ZHIPU_CHAT_COMPLETIONS_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


@dataclass
class SearchResultDraft:
    candidate: RagQueryCandidate
    before_context: str
    after_context: str
    answer_status: SearchResultAnswerStatus
    answer: str | None = None
    answer_error: str | None = None


@dataclass
class AnswerBatch:
    answers_by_rank: dict[int, tuple[SearchResultAnswerStatus, str | None]]
    latency_ms: int
    raw_text: str


def run_search(db: Session, request: SearchRequest) -> SearchResponse:
    debug_response = run_debug_query(
        db,
        DebugQueryRequest(
            question=request.question,
            use_llm=False,
            final_top_k=SEARCH_RESULT_TOP_K,
        ),
    )
    query_log_id = debug_response.query_log_id
    if query_log_id is None:
        raise RuntimeError("debug query did not create a query log")

    warnings = list(debug_response.diagnostics.warnings)
    candidate_rows = _selected_candidate_rows(db, query_log_id)
    drafts = [
        SearchResultDraft(
            candidate=candidate,
            before_context=_context_for_neighbor(db, candidate, offset=-1),
            after_context=_context_for_neighbor(db, candidate, offset=1),
            answer_status=SearchResultAnswerStatus.LLM_DISABLED,
        )
        for candidate in candidate_rows
    ]

    prompt: str | None = None
    llm_latency_ms: int | None = None
    llm_error: str | None = None
    status = SearchStatus.COMPLETED

    if not drafts:
        status = SearchStatus.NO_RECALL
    elif not request.use_llm:
        status = SearchStatus.LLM_DISABLED
    else:
        settings = get_settings()
        if settings.llm_provider == "none":
            status = SearchStatus.LLM_DISABLED
        else:
            prompt = build_result_prompt(request.question, drafts)
            try:
                batch = generate_result_answers(settings, prompt)
                llm_latency_ms = batch.latency_ms
                _apply_answer_batch(drafts, batch)
            except Exception as exc:
                status = SearchStatus.LLM_ERROR
                llm_error = str(exc)
                for draft in drafts:
                    draft.answer_status = SearchResultAnswerStatus.LLM_ERROR
                    draft.answer = None
                    draft.answer_error = llm_error

    if status == SearchStatus.LLM_DISABLED:
        for draft in drafts:
            draft.answer_status = SearchResultAnswerStatus.LLM_DISABLED
            draft.answer = None

    _persist_search_snapshots(
        db,
        query_log_id=query_log_id,
        request=request,
        prompt=prompt,
        drafts=drafts,
        llm_latency_ms=llm_latency_ms,
        llm_error=llm_error,
    )

    return SearchResponse(
        query_log_id=query_log_id,
        question=request.question,
        status=status,
        results=[_result_response(draft) for draft in drafts],
        warnings=warnings,
    )


def create_search_feedback(
    db: Session,
    query_log_id: int,
    request: SearchFeedbackRequest,
    user: AuthUser,
) -> SearchFeedbackResponse | None:
    query_log = db.get(RagQueryLog, query_log_id)
    if query_log is None:
        return None

    feedback = RagQueryFeedback(
        query_log_id=query_log_id,
        username=user.username,
        role=user.role,
        rating=request.rating,
        comment=request.comment,
        expected_answer=request.expected_answer,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return SearchFeedbackResponse.model_validate(feedback)


def build_result_prompt(question: str, drafts: list[SearchResultDraft]) -> str:
    blocks: list[str] = []
    for draft in drafts:
        candidate = draft.candidate
        section = candidate.heading_path or candidate.section_title or "未分章节"
        blocks.append(
            "\n".join(
                [
                    f"[结果{candidate.rank}]",
                    f"rank：{candidate.rank}",
                    f"文档：{candidate.document_name}",
                    f"章节：{section}",
                    "前文：",
                    draft.before_context or "无",
                    "命中内容：",
                    candidate.content_snapshot,
                    "后文：",
                    draft.after_context or "无",
                ]
            )
        )

    return (
        "你是一个知识库检索结果回答助手。\n\n"
        "回答规则：\n"
        "1. 必须为每条检索结果分别生成 answer。\n"
        "2. 每条 answer 只能根据该条结果的前文、命中内容和后文回答，不能使用其他结果的信息。\n"
        "3. 只要该条资料能回答用户问题的全部或一部分，answer_status 必须使用 ANSWERED，并在 answer 中说明该片段能支持的结论。\n"
        "4. 不能因为资料只覆盖部分答案就返回 NO_ANSWER；只有该条资料与问题无关，或完全无法支持任何答案时，才使用 NO_ANSWER，answer 使用 null。\n"
        "5. 如果可以回答，answer_status 使用 ANSWERED，answer 要简洁、直接。\n"
        "6. 只输出严格 JSON，不要输出 Markdown 或额外解释。\n\n"
        "JSON 格式：\n"
        '{"results":[{"rank":1,"answer_status":"ANSWERED","answer":"..."}]}\n\n'
        f"用户问题：\n{question}\n\n"
        "检索结果资料：\n"
        + "\n\n".join(blocks)
    )


def generate_result_answers(settings: Settings, prompt: str) -> AnswerBatch:
    started_at = time.perf_counter()
    if settings.llm_provider == "zhipu":
        raw_text = _call_zhipu_chat(settings, prompt)
    elif settings.llm_provider == "minimax":
        raw_text = _call_minimax_chat(settings, prompt)
    else:
        raise RuntimeError(f"unsupported LLM provider: {settings.llm_provider}")
    return AnswerBatch(
        answers_by_rank=_parse_answer_payload(raw_text),
        latency_ms=max(0, round((time.perf_counter() - started_at) * 1000)),
        raw_text=raw_text,
    )


def _selected_candidate_rows(db: Session, query_log_id: int) -> list[RagQueryCandidate]:
    return list(
        db.scalars(
            select(RagQueryCandidate)
            .where(RagQueryCandidate.query_log_id == query_log_id)
            .where(RagQueryCandidate.selected_for_prompt.is_(True))
            .order_by(RagQueryCandidate.rank.asc(), RagQueryCandidate.id.asc())
        )
    )


def _context_for_neighbor(db: Session, candidate: RagQueryCandidate, *, offset: int) -> str:
    if candidate.parent_chunk_id is None or candidate.child_index is None:
        return ""
    neighbor = db.scalar(
        select(RagChunk)
        .where(RagChunk.document_version_id == candidate.document_version_id)
        .where(RagChunk.parent_chunk_id == candidate.parent_chunk_id)
        .where(RagChunk.chunk_type == "CHILD")
        .where(RagChunk.child_index == candidate.child_index + offset)
        .limit(1)
    )
    if neighbor is None:
        return ""
    content = neighbor.content.strip()
    if offset < 0:
        return content[-CONTEXT_WINDOW_CHARS:]
    return content[:CONTEXT_WINDOW_CHARS]


def _apply_answer_batch(drafts: list[SearchResultDraft], batch: AnswerBatch) -> None:
    for draft in drafts:
        answer_status, answer = batch.answers_by_rank.get(
            draft.candidate.rank,
            (SearchResultAnswerStatus.NO_ANSWER, None),
        )
        draft.answer_status = answer_status
        draft.answer = answer if answer_status == SearchResultAnswerStatus.ANSWERED else None
        draft.answer_error = None


def _persist_search_snapshots(
    db: Session,
    *,
    query_log_id: int,
    request: SearchRequest,
    prompt: str | None,
    drafts: list[SearchResultDraft],
    llm_latency_ms: int | None,
    llm_error: str | None,
) -> None:
    settings = get_settings()
    query_log = db.get(RagQueryLog, query_log_id)
    if query_log is not None:
        query_log.use_llm = request.use_llm
        query_log.answer_prompt_version = RESULT_PROMPT_VERSION if prompt else None
        query_log.answer_prompt_text = prompt
        query_log.llm_model = settings.llm_model if request.use_llm and settings.llm_provider != "none" else None
        query_log.model_config_snapshot = {
            **(query_log.model_config_snapshot or {}),
            "llm": {
                "provider": settings.llm_provider,
                "model": settings.llm_model if request.use_llm and settings.llm_provider != "none" else None,
            },
        }
        query_log.llm_latency_ms = llm_latency_ms
        query_log.llm_error = llm_error
        if llm_latency_ms is not None:
            query_log.total_latency_ms = (query_log.total_latency_ms or 0) + llm_latency_ms

    for draft in drafts:
        candidate = draft.candidate
        candidate.result_answer = draft.answer
        candidate.result_answer_status = draft.answer_status
        candidate.result_answer_error = draft.answer_error
        candidate.before_context_snapshot = draft.before_context
        candidate.after_context_snapshot = draft.after_context
    db.commit()


def _result_response(draft: SearchResultDraft) -> SearchResultResponse:
    candidate = draft.candidate
    return SearchResultResponse(
        rank=candidate.rank,
        query_candidate_id=candidate.id,
        chunk_id=candidate.chunk_id,
        answer_status=draft.answer_status,
        answer=draft.answer,
        document_id=candidate.document_id,
        document_name=candidate.document_name,
        section_title=candidate.section_title,
        heading_path=candidate.heading_path,
        hit_content=candidate.content_snapshot,
        before_context=draft.before_context,
        after_context=draft.after_context,
    )


def _call_zhipu_chat(settings: Settings, prompt: str) -> str:
    if not settings.zhipuai_api_key:
        raise RuntimeError("ZHIPUAI_API_KEY is required when LLM_PROVIDER=zhipu")
    with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
        response = client.post(
            ZHIPU_CHAT_COMPLETIONS_URL,
            headers={"Authorization": f"Bearer {settings.zhipuai_api_key}"},
            json={
                "model": settings.llm_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": settings.llm_temperature,
                "max_tokens": settings.llm_max_tokens,
            },
        )
        response.raise_for_status()
        payload = response.json()
    try:
        return str(payload["choices"][0]["message"]["content"])
    except Exception as exc:
        raise RuntimeError("LLM response did not include message content") from exc


def _call_minimax_chat(settings: Settings, prompt: str) -> str:
    if not settings.minimax_api_key:
        raise RuntimeError("MINIMAX_API_KEY is required when LLM_PROVIDER=minimax")
    return _call_openai_compatible_chat(
        api_key=settings.minimax_api_key,
        base_url=settings.minimax_api_base_url,
        model=settings.llm_model,
        prompt=prompt,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        timeout=settings.llm_timeout_seconds,
    )


def _call_openai_compatible_chat(
    *,
    api_key: str,
    base_url: str,
    model: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    timeout: int,
) -> str:
    with httpx.Client(timeout=timeout) as client:
        response = client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        response.raise_for_status()
        payload = response.json()
    try:
        return str(payload["choices"][0]["message"]["content"])
    except Exception as exc:
        raise RuntimeError("LLM response did not include message content") from exc


def _parse_answer_payload(raw_text: str) -> dict[int, tuple[SearchResultAnswerStatus, str | None]]:
    payload = json.loads(_extract_json_object(raw_text))
    answers: dict[int, tuple[SearchResultAnswerStatus, str | None]] = {}
    for item in payload.get("results", []):
        try:
            rank = int(item["rank"])
        except Exception:
            continue
        answer = item.get("answer")
        normalized_answer = answer.strip() if isinstance(answer, str) and answer.strip() else None
        try:
            status = SearchResultAnswerStatus(
                str(item.get("answer_status") or SearchResultAnswerStatus.NO_ANSWER).upper()
            )
        except ValueError:
            status = SearchResultAnswerStatus.ANSWERED if normalized_answer else SearchResultAnswerStatus.NO_ANSWER
        if status == SearchResultAnswerStatus.NO_ANSWER and normalized_answer:
            status = SearchResultAnswerStatus.ANSWERED
        answers[rank] = (status, normalized_answer)
    return answers


def _extract_json_object(raw_text: str) -> str:
    stripped = raw_text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end <= start:
        raise RuntimeError("LLM response is not valid JSON")
    return stripped[start : end + 1]
