from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_authenticated_user
from app.core.errors import DocumentNotFoundError, UploadValidationError
from app.repositories.document_repo import DocumentRepository
from app.schemas.document import (
    ChunkListResponse,
    ChunkResponse,
    DeleteDocumentResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentVersionResponse,
    UploadDocumentResponse,
)
from app.services.ingest_service import ingest_document

# 文档模块路由：集中处理上传、查询、版本查看和软删除等 HTTP 入口。
router = APIRouter(prefix="/documents", tags=["documents"], dependencies=[Depends(require_authenticated_user)])


# 新文档上传入口；具体入库、解析、切块和向量化流程交给 ingestion service。
@router.post("/upload", response_model=UploadDocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> UploadDocumentResponse:
    return await _handle_upload(db=db, file=file)


# 现有文档的新版本上传入口；成功后新版本会成为当前版本。
@router.post("/{document_id}/versions/upload", response_model=UploadDocumentResponse)
async def upload_document_version(
    document_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> UploadDocumentResponse:
    return await _handle_upload(db=db, file=file, document_id=document_id)


# 获取当前未删除的文档列表。
@router.get("", response_model=DocumentListResponse)
def list_documents(db: Session = Depends(get_db)) -> DocumentListResponse:
    documents = DocumentRepository().list_active(db)
    return DocumentListResponse(items=[DocumentResponse.model_validate(item) for item in documents])


# 获取文档详情和版本列表。
@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document(document_id: int, db: Session = Depends(get_db)) -> DocumentDetailResponse:
    repo = DocumentRepository()
    document = repo.get_active(db, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")

    versions = repo.list_versions(db, document_id=document.id)
    return DocumentDetailResponse(
        id=document.id,
        name=document.name,
        file_type=document.file_type,
        file_size=document.file_size,
        current_version_id=document.current_version_id,
        status=document.status,
        created_at=document.created_at,
        updated_at=document.updated_at,
        versions=[DocumentVersionResponse.model_validate(version) for version in versions],
    )


# 获取文档 chunk；默认读取当前版本，也支持指定历史 version id。
@router.get("/{document_id}/chunks", response_model=ChunkListResponse)
def list_document_chunks(
    document_id: int,
    version: str = Query(default="current"),
    chunk_type: str = Query(default="CHILD"),
    db: Session = Depends(get_db),
) -> ChunkListResponse:
    repo = DocumentRepository()
    document = repo.get_active(db, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")

    if version == "current":
        if document.current_version_id is None:
            raise HTTPException(status_code=404, detail="document has no completed version")
        version_id = document.current_version_id
    else:
        try:
            version_id = int(version)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="version must be 'current' or a version id") from exc

    chunks = repo.list_chunks(
        db,
        document_id=document_id,
        document_version_id=version_id,
        chunk_type=chunk_type.upper(),
    )
    return ChunkListResponse(items=[ChunkResponse.model_validate(item) for item in chunks])


# 删除文档采用软删除，保留版本和 chunk 数据用于审计或后续恢复。
@router.delete("/{document_id}", response_model=DeleteDocumentResponse)
def delete_document(document_id: int, db: Session = Depends(get_db)) -> DeleteDocumentResponse:
    repo = DocumentRepository()
    document = repo.get_active(db, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    repo.soft_delete(db, document)
    db.commit()
    return DeleteDocumentResponse(success=True)


async def _handle_upload(
    db: Session,
    file: UploadFile,
    document_id: int | None = None,
) -> UploadDocumentResponse:
    # 上传入口共用处理：route 层只负责读取文件和映射 HTTP 异常。
    try:
        # 入库流程需要原始字节用于 hash、解析、存储和 embedding。
        file_bytes = await file.read()
        result = ingest_document(
            db=db,
            file_bytes=file_bytes,
            filename=file.filename or "upload",
            content_type=file.content_type or "application/octet-stream",
            document_id=document_id,
        )
        return UploadDocumentResponse(**result)
    except UploadValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
