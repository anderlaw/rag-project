from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    file_type: str | None = None
    file_size: int | None = None
    current_version_id: int | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class DocumentVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version_no: int
    file_hash: str | None = None
    original_filename: str | None = None
    storage_key: str | None = None
    parser_version: str | None = None
    parser_config_snapshot: dict[str, Any] | None = None
    chunk_strategy_name: str | None = None
    chunk_config_snapshot: dict[str, Any] | None = None
    status: str
    chunk_count: int
    error_message: str | None = None
    created_at: datetime
    processed_at: datetime | None = None


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]


class DocumentDetailResponse(DocumentResponse):
    versions: list[DocumentVersionResponse]


class UploadDocumentResponse(BaseModel):
    document_id: int
    version_id: int
    status: str
    chunk_count: int
    current_version_id: int | None = None


class ChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chunk_type: str
    parent_chunk_id: int | None = None
    chunk_index: int
    child_index: int | None = None
    heading_path: str | None = None
    section_title: str | None = None
    start_char: int | None = None
    end_char: int | None = None
    content: str
    content_with_context: str | None = None
    search_text: str | None = None
    search_tsv: str | None = None


class ChunkListResponse(BaseModel):
    items: list[ChunkResponse]


class DeleteDocumentResponse(BaseModel):
    success: bool
