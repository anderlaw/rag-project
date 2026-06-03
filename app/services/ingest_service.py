from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import DocumentNotFoundError, UploadValidationError
from app.repositories.document_repo import DocumentRepository
from app.services.chunker import Chunker
from app.services.document_parser import DocumentParser
from app.services.embedding import create_embedding_service
from app.services.storage import create_storage_service
from app.utils.hash import sha256_hex


def ingest_document(
    *,
    db: Session,
    file_bytes: bytes,
    filename: str,
    content_type: str,
    document_id: int | None = None,
) -> dict:
    settings = get_settings()
    _validate_upload(filename=filename, file_bytes=file_bytes)

    repo = DocumentRepository()
    parser = DocumentParser()
    chunker = Chunker(settings)
    storage = create_storage_service(settings)
    embedding_service = create_embedding_service(settings)

    file_type = Path(filename).suffix.lower().lstrip(".")
    file_hash = sha256_hex(file_bytes)

    if document_id is None:
        document = repo.create_document(db, name=filename, file_type=file_type, file_size=len(file_bytes))
    else:
        document = repo.get_active(db, document_id)
        if document is None:
            raise DocumentNotFoundError("document not found")

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
        version.storage_key = storage.save(
            file_bytes=file_bytes,
            filename=filename,
            content_type=content_type,
            document_id=document.id,
            version_id=version.id,
        )
        db.commit()

        blocks = parser.parse(filename=filename, file_bytes=file_bytes)
        if not blocks:
            raise ValueError("document has no extractable text")

        chunk_groups = chunker.build_parent_child_chunks(blocks)
        child_chunks = [child for group in chunk_groups for child in group.children]
        embeddings = embedding_service.embed([child.content_with_context for child in child_chunks])
        for child, embedding in zip(child_chunks, embeddings, strict=True):
            child.embedding = embedding

        created_chunk_count = 0
        for group in chunk_groups:
            parent = repo.create_chunk(
                db,
                document_id=document.id,
                document_version_id=version.id,
                parent_chunk_id=None,
                **group.parent.__dict__,
            )
            created_chunk_count += 1

            for child in group.children:
                repo.create_chunk(
                    db,
                    document_id=document.id,
                    document_version_id=version.id,
                    parent_chunk_id=parent.id,
                    **child.__dict__,
                )
                created_chunk_count += 1

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
        db.rollback()
        failed_version = db.get(type(version), version.id)
        if failed_version is not None:
            repo.delete_chunks_by_version(db, version_id=version.id)
            repo.mark_version_failed(failed_version, error_message=str(exc))
            db.commit()
        raise


def _validate_upload(*, filename: str, file_bytes: bytes) -> None:
    settings = get_settings()
    extension = Path(filename).suffix.lower().lstrip(".")
    if not extension or extension not in settings.allowed_upload_extensions:
        allowed = ", ".join(settings.allowed_upload_extensions)
        raise UploadValidationError(f"file extension '{extension or '<none>'}' is not allowed; allowed: {allowed}")
    if not file_bytes:
        raise UploadValidationError("uploaded file is empty")
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise UploadValidationError(f"uploaded file exceeds {settings.max_upload_size_mb} MB")
