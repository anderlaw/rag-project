from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import RagChunk, RagDocument, RagDocumentVersion


class DocumentRepository:
    def create_document(self, db: Session, *, name: str, file_type: str, file_size: int) -> RagDocument:
        document = RagDocument(name=name, file_type=file_type, file_size=file_size, status="ACTIVE")
        db.add(document)
        db.flush()
        return document

    def get_active(self, db: Session, document_id: int) -> RagDocument | None:
        return db.scalar(
            select(RagDocument).where(
                RagDocument.id == document_id,
                RagDocument.status == "ACTIVE",
            )
        )

    def list_active(self, db: Session) -> list[RagDocument]:
        return list(
            db.scalars(
                select(RagDocument)
                .where(RagDocument.status == "ACTIVE")
                .order_by(RagDocument.created_at.desc(), RagDocument.id.desc())
            )
        )

    # 基于当前最大 version_no 生成下一个版本号，避免调用方重复拼装查询。
    def next_version_no(self, db: Session, *, document_id: int) -> int:
        max_version = db.scalar(
            select(func.max(RagDocumentVersion.version_no)).where(RagDocumentVersion.document_id == document_id)
        )
        return int(max_version or 0) + 1

    def create_version(
        self,
        db: Session,
        *,
        document_id: int,
        version_no: int,
        file_hash: str,
        original_filename: str,
        parser_version: str,
        parser_config_snapshot: dict,
        chunk_strategy_name: str,
        chunk_config_snapshot: dict,
    ) -> RagDocumentVersion:
        # 新版本先进入 PROCESSING，解析和 chunk 持久化完成后再标记 COMPLETED。
        version = RagDocumentVersion(
            document_id=document_id,
            version_no=version_no,
            file_hash=file_hash,
            original_filename=original_filename,
            parser_version=parser_version,
            parser_config_snapshot=parser_config_snapshot,
            chunk_strategy_name=chunk_strategy_name,
            chunk_config_snapshot=chunk_config_snapshot,
            status="PROCESSING",
        )
        db.add(version)
        db.flush()
        return version

    def list_versions(self, db: Session, *, document_id: int) -> list[RagDocumentVersion]:
        return list(
            db.scalars(
                select(RagDocumentVersion)
                .where(RagDocumentVersion.document_id == document_id)
                .order_by(RagDocumentVersion.version_no.asc())
            )
        )

    def mark_version_completed(self, version: RagDocumentVersion, *, chunk_count: int) -> None:
        version.status = "COMPLETED"
        version.chunk_count = chunk_count
        version.error_message = None
        version.processed_at = datetime.utcnow()

    def mark_version_failed(self, version: RagDocumentVersion, *, error_message: str) -> None:
        version.status = "FAILED"
        version.error_message = error_message
        version.processed_at = datetime.utcnow()

    def set_current_version(self, document: RagDocument, *, version_id: int) -> None:
        document.current_version_id = version_id
        document.updated_at = datetime.utcnow()

    def create_chunk(self, db: Session, **values) -> RagChunk:
        chunk = RagChunk(**values)
        db.add(chunk)
        db.flush()
        return chunk

    def delete_chunks_by_version(self, db: Session, *, version_id: int) -> None:
        for chunk in db.scalars(select(RagChunk).where(RagChunk.document_version_id == version_id)):
            db.delete(chunk)

    def list_chunks(
        self,
        db: Session,
        *,
        document_id: int,
        document_version_id: int,
        chunk_type: str,
    ) -> list[RagChunk]:
        return list(
            db.scalars(
                select(RagChunk)
                .where(
                    RagChunk.document_id == document_id,
                    RagChunk.document_version_id == document_version_id,
                    RagChunk.chunk_type == chunk_type,
                )
                .order_by(RagChunk.chunk_index.asc(), RagChunk.child_index.asc().nullsfirst())
            )
        )

    def soft_delete(self, db: Session, document: RagDocument) -> None:
        document.status = "DELETED"
        document.updated_at = datetime.utcnow()
        db.add(document)
