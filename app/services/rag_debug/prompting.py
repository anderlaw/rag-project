from app.schemas.rag import DebugLlmResponse, DebugPromptResponse
from app.services.rag_debug.types import CandidateDraft

ANSWER_PROMPT_VERSION = "rag_qa_v1"
NO_RECALL_ANSWER = "根据当前资料无法确定。"


def build_prompt(question: str, selected_candidates: list[CandidateDraft]) -> DebugPromptResponse:
    # Prompt 只拼接最终入选片段，保证 LLM 看到的资料与 selected_chunks 一致。
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


def build_llm_response(*, use_llm: bool, has_selected_chunks: bool) -> DebugLlmResponse:
    # LLM 尚未接入真实 provider；这里保留响应结构和无召回时的固定兜底答案。
    if not use_llm:
        return DebugLlmResponse(used=False, answer=None)
    if not has_selected_chunks:
        return DebugLlmResponse(used=False, answer=NO_RECALL_ANSWER)
    return DebugLlmResponse(used=False, error="LLM provider is not configured")
