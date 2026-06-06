from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.repositories.document_repo import DocumentRepository
from app.services.chunker import Chunker
from app.services.document_parser import DocumentParser
from app.services.embedding import create_embedding_service
from app.services.ingestion.pipeline import ingest_document_pipeline
from app.services.ingestion.validation import validate_upload
from app.services.storage import create_storage_service


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
    # 外层入口只负责组装文档仓库、解析、切块、存储和 embedding 依赖。
    repo = DocumentRepository()
    parser = DocumentParser()
    chunker = Chunker(settings)
    storage = create_storage_service(settings)

    return ingest_document_pipeline(
        db=db,
        settings=settings,
        repo=repo,
        parser=parser,
        chunker=chunker,
        storage=storage,
        embedding_service_factory=create_embedding_service,
        file_bytes=file_bytes,
        filename=filename,
        content_type=content_type,
        document_id=document_id,
    )


def _validate_upload(*, filename: str, file_bytes: bytes) -> None:
    # 保留旧私有函数名，兼容现有调用方；实际校验逻辑收敛到 ingestion.validation。
    settings = get_settings()
    validate_upload(settings=settings, filename=filename, file_bytes=file_bytes)
