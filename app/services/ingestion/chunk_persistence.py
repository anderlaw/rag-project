from typing import Any

from sqlalchemy.orm import Session

from app.repositories.document_repo import DocumentRepository
from app.services.chunker import ChunkDraft, ChunkGroup


def persist_chunk_groups(
    *,
    db: Session,
    repo: DocumentRepository,
    document_id: int,
    version_id: int,
    chunk_groups: list[ChunkGroup],
) -> int:
    created_chunk_count = 0
    for group in chunk_groups:
        parent = repo.create_chunk(
            db,
            document_id=document_id,
            document_version_id=version_id,
            parent_chunk_id=None,
            **chunk_draft_values(group.parent),
        )
        created_chunk_count += 1

        for child in group.children:
            repo.create_chunk(
                db,
                document_id=document_id,
                document_version_id=version_id,
                parent_chunk_id=parent.id,
                **chunk_draft_values(child),
            )
            created_chunk_count += 1
    return created_chunk_count


def chunk_draft_values(chunk: ChunkDraft) -> dict[str, Any]:
    # 显式映射 ChunkDraft 字段，避免未来新增内部属性时被误写入数据库。
    return {
        "chunk_type": chunk.chunk_type,
        "chunk_index": chunk.chunk_index,
        "child_index": chunk.child_index,
        "heading_path": chunk.heading_path,
        "section_title": chunk.section_title,
        "start_char": chunk.start_char,
        "end_char": chunk.end_char,
        "content": chunk.content,
        "content_with_context": chunk.content_with_context,
        "search_text": chunk.search_text,
        "search_tsv": chunk.search_tsv,
        "embedding": chunk.embedding,
    }
