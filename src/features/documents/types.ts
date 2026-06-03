export type DocumentStatus = "ACTIVE" | "DELETED" | string;
export type VersionStatus = "PROCESSING" | "COMPLETED" | "FAILED" | string;
export type ChunkType = "PARENT" | "CHILD";
export type JsonObject = Record<string, unknown>;

export type DocumentSummary = {
  id: number;
  name: string;
  file_type: string | null;
  file_size: number | null;
  current_version_id: number | null;
  status: DocumentStatus;
  created_at: string;
  updated_at: string;
};

export type DocumentVersion = {
  id: number;
  version_no: number;
  file_hash: string | null;
  original_filename: string | null;
  storage_key: string | null;
  parser_version: string | null;
  parser_config_snapshot: JsonObject | null;
  chunk_strategy_name: string | null;
  chunk_config_snapshot: JsonObject | null;
  status: VersionStatus;
  chunk_count: number;
  error_message: string | null;
  created_at: string;
  processed_at: string | null;
};

export type DocumentDetail = DocumentSummary & {
  versions: DocumentVersion[];
};

export type DocumentChunk = {
  id: number;
  chunk_type: ChunkType | string;
  parent_chunk_id: number | null;
  chunk_index: number;
  child_index: number | null;
  heading_path: string | null;
  section_title: string | null;
  start_char: number | null;
  end_char: number | null;
  content: string;
  content_with_context: string | null;
  search_text: string | null;
  search_tsv: string | null;
};

export type DocumentListResponse = {
  items: DocumentSummary[];
};

export type ChunkListResponse = {
  items: DocumentChunk[];
};

export type UploadDocumentResponse = {
  document_id: number;
  version_id: number;
  status: VersionStatus;
  chunk_count: number;
  current_version_id: number | null;
};

export type DeleteDocumentResponse = {
  success: boolean;
};
