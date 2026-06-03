import { requestJson } from "../../lib/http";
import type {
  ChunkListResponse,
  ChunkType,
  DeleteDocumentResponse,
  DocumentDetail,
  DocumentListResponse,
  UploadDocumentResponse
} from "./types";

const DOCUMENTS_BASE = "/api/v1/documents";

export function listDocuments(): Promise<DocumentListResponse> {
  return requestJson<DocumentListResponse>(DOCUMENTS_BASE);
}

export function getDocument(documentId: number): Promise<DocumentDetail> {
  return requestJson<DocumentDetail>(`${DOCUMENTS_BASE}/${documentId}`);
}

export function listDocumentChunks(
  documentId: number,
  version: "current" | number = "current",
  chunkType: ChunkType = "CHILD"
): Promise<ChunkListResponse> {
  const params = new URLSearchParams({
    version: String(version),
    chunk_type: chunkType
  });
  return requestJson<ChunkListResponse>(`${DOCUMENTS_BASE}/${documentId}/chunks?${params.toString()}`);
}

export function uploadDocument(file: File): Promise<UploadDocumentResponse> {
  const body = new FormData();
  body.append("file", file);
  return requestJson<UploadDocumentResponse>(`${DOCUMENTS_BASE}/upload`, {
    method: "POST",
    body
  });
}

export function uploadDocumentVersion(documentId: number, file: File): Promise<UploadDocumentResponse> {
  const body = new FormData();
  body.append("file", file);
  return requestJson<UploadDocumentResponse>(`${DOCUMENTS_BASE}/${documentId}/versions/upload`, {
    method: "POST",
    body
  });
}

export function deleteDocument(documentId: number): Promise<DeleteDocumentResponse> {
  return requestJson<DeleteDocumentResponse>(`${DOCUMENTS_BASE}/${documentId}`, {
    method: "DELETE"
  });
}
