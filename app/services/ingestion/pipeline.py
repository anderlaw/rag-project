from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import DocumentNotFoundError
from app.repositories.document_repo import DocumentRepository
from app.services.chunker import Chunker
from app.services.document_parser import DocumentParser
from app.services.ingestion.chunk_persistence import persist_chunk_groups
from app.services.storage import StorageService
from app.utils.hash import sha256_hex


def ingest_document_pipeline(
    *,
    db: Session,
    settings: Settings,
    repo: DocumentRepository,
    parser: DocumentParser,
    chunker: Chunker,
    storage: StorageService,
    embedding_service_factory: Callable[[Settings], Any],
    file_bytes: bytes,
    filename: str,
    content_type: str,
    document_id: int | None,
) -> dict:
    file_type = Path(filename).suffix.lower().lstrip(".")
    file_hash = sha256_hex(file_bytes)

    # 新文档先创建 document；上传历史版本时必须确认原文档仍处于 ACTIVE 状态。
    if document_id is None:
        document = repo.create_document(db, name=filename, file_type=file_type, file_size=len(file_bytes))
    else:
        document = repo.get_active(db, document_id)
        if document is None:
            raise DocumentNotFoundError("document not found")

    # 版本先落库为 PROCESSING，后续任一步失败都能把失败状态记录到该版本上。
    version = repo.create_version(
        db,
        document_id=document.id,
        version_no=repo.next_version_no(db, document_id=document.id),
        file_hash=file_hash,
        original_filename=filename,
        parser_version=parser.version,
        parser_config_snapshot=parser.config_snapshot(),
        chunk_strategy_name=chunker.strategy_name,
        chunk_config_snapshot=chunker.config_snapshot(),
    )
    db.commit()
    db.refresh(document)
    db.refresh(version)

    try:
        # 先保存原始文件，再进入解析和 chunk 生成；storage_key 会记录在当前版本上。
        version.storage_key = storage.save(
            file_bytes=file_bytes,
            filename=filename,
            content_type=content_type,
            document_id=document.id,
            version_id=version.id,
        )
        db.commit()

        # 解析文档后生成父子 chunk；空文本直接失败，避免创建不可检索版本。
        blocks = parser.parse(filename=filename, file_bytes=file_bytes)
        if not blocks:
            raise ValueError("document has no extractable text")

        chunk_groups = chunker.build_parent_child_chunks(blocks, document_name=filename)
        # 展平所有子 chunk 后批量请求 embedding，减少外部 API 调用次数。
        child_chunks = [child for group in chunk_groups for child in group.children]
        embeddings = embedding_service_factory(settings).embed([child.content_with_context for child in child_chunks])

        # 向量结果按输入顺序写回子 chunk，父 chunk 只保留文本和结构信息。
        for child, embedding in zip(child_chunks, embeddings, strict=True):
            child.embedding = embedding

        created_chunk_count = persist_chunk_groups(
            db=db,
            repo=repo,
            document_id=document.id,
            version_id=version.id,
            chunk_groups=chunk_groups,
        )
        # 切片写入成功后，版本标记 COMPLETED，并把文档 current_version 指向该版本。
        repo.mark_version_completed(version, chunk_count=created_chunk_count)
        document.name = filename
        document.file_type = file_type
        document.file_size = len(file_bytes)
        repo.set_current_version(document, version_id=version.id)
        db.commit()
        db.refresh(document)
        db.refresh(version)

        return {
            "document_id": document.id,
            "version_id": version.id,
            "status": version.status,
            "chunk_count": version.chunk_count,
            "current_version_id": document.current_version_id,
        }
    except Exception as exc:
        # 失败的新版本不能成为 current；回滚后删除该版本已写入的 chunk，并记录失败原因。
        db.rollback()
        failed_version = db.get(type(version), version.id)
        if failed_version is not None:
            repo.delete_chunks_by_version(db, version_id=version.id)
            repo.mark_version_failed(failed_version, error_message=str(exc))
            db.commit()
        raise
