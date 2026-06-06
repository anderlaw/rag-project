from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.document import RagChunk, RagDocument, RagDocumentVersion
from app.schemas.rag import DebugDocumentDiagnosticsResponse, DebugDocumentStatusMatchResponse
from app.services.rag_debug.scoring import (
    character_coverage_score,
    is_low_information_chunk,
    keyword_score,
)
from app.services.rag_debug.scoring_rules import DIAGNOSTIC_RELATED_MATCH_MIN_SCORE


def list_searchable_chunks(db: Session) -> list[tuple[RagChunk, str]]:
    # 列出可供搜索的 CHILD chunk，并带上所属文档名用于字段打分和候选响应。
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


def filter_candidate_chunks(chunks: list[tuple[RagChunk, str]]) -> list[tuple[RagChunk, str]]:
    # 候选阶段先剔除低信息 chunk，避免它们占用 vector/keyword/trgm top_k 名额和前端候选列表。
    return [(chunk, document_name) for chunk, document_name in chunks if not is_low_information_chunk(chunk)]


def build_document_diagnostics(
    db: Session,
    question: str,
    *,
    searchable_child_chunk_count: int | None = None,
) -> DebugDocumentDiagnosticsResponse:
    # 诊断当前文档库状态，找出与查询相关但未参与检索的文档，并给出提示。
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
    # 只取最近 80 条被排除在检索外的文档，避免诊断查询拖慢调试接口。
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
        chunks = list_document_current_child_chunks(db, document)
        match_reason = diagnostic_match_reason(question, document, chunks)
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
        # 整理警告信息，帮助前端解释“为什么相关内容没有参与检索”。
        warnings.append(
            f"发现 {len(related_documents)} 个相关文档未参与检索，可能是状态非 ACTIVE 或当前版本不可检索。"
        )

    return DebugDocumentDiagnosticsResponse(
        active_document_count=active_document_count,
        searchable_child_chunk_count=searchable_child_chunk_count,
        inactive_related_documents=related_documents[:10],
        warnings=warnings,
    )


def list_document_current_child_chunks(db: Session, document: RagDocument) -> list[RagChunk]:
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


def diagnostic_match_reason(question: str, document: RagDocument, chunks: list[RagChunk]) -> str | None:
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
    coverage = character_coverage_score(question, haystack)
    if (
        coverage < DIAGNOSTIC_RELATED_MATCH_MIN_SCORE
        and keyword_score(question, haystack) < DIAGNOSTIC_RELATED_MATCH_MIN_SCORE
    ):
        return None
    return "文档名/标题/内容与问题关键词匹配"
