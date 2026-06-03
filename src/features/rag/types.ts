export type DebugQueryRequest = {
  question: string;
  search_profile_id?: number | null;
  use_llm: boolean;
  vector_top_k?: number;
  keyword_top_k?: number;
  trgm_top_k?: number;
  final_top_k?: number;
  vector_weight?: number;
  keyword_weight?: number;
  trgm_weight?: number;
  min_final_score?: number;
};

export type DebugSearchProfile = {
  id: number | null;
  name: string;
  mode: string;
  vector_top_k: number;
  keyword_top_k: number;
  trgm_top_k: number;
  final_top_k: number;
  vector_weight: number;
  keyword_weight: number;
  trgm_weight: number;
  min_final_score: number;
};

export type DebugCandidate = {
  rank: number;
  chunk_id: number;
  document_id: number;
  document_version_id: number;
  document_name: string;
  section_title: string | null;
  heading_path: string | null;
  parent_chunk_id: number | null;
  chunk_index: number;
  child_index: number | null;
  start_char: number | null;
  end_char: number | null;
  page_number: number | null;
  vector_score: number;
  keyword_score: number;
  trgm_score: number;
  final_score: number;
  selected_for_prompt: boolean;
  content_preview: string;
  content: string;
  content_with_context: string | null;
};

export type DebugPrompt = {
  version: string;
  text: string;
};

export type DebugLlm = {
  used: boolean;
  model: string | null;
  latency_ms: number | null;
  answer: string | null;
  error: string | null;
};

export type DebugDocumentStatusMatch = {
  document_id: number;
  name: string;
  status: string;
  current_version_id: number | null;
  version_status: string | null;
  chunk_count: number | null;
  match_reason: string;
};

export type DebugDocumentDiagnostics = {
  active_document_count: number;
  searchable_child_chunk_count: number;
  inactive_related_documents: DebugDocumentStatusMatch[];
  warnings: string[];
};

export type DebugQueryResponse = {
  query_log_id: number | null;
  question: string;
  search_profile: DebugSearchProfile;
  candidates: DebugCandidate[];
  selected_chunks: DebugCandidate[];
  prompt: DebugPrompt | null;
  diagnostics: DebugDocumentDiagnostics;
  llm: DebugLlm;
};

export type QueryLogDetail = {
  id: number;
  question: string;
  search_mode: string;
  use_llm: boolean;
  created_at: string;
  search_profile: DebugSearchProfile;
  model_config_snapshot: Record<string, unknown> | null;
  search_latency_ms: number | null;
  llm_latency_ms: number | null;
  total_latency_ms: number | null;
  candidates: DebugCandidate[];
  selected_chunks: DebugCandidate[];
  prompt: DebugPrompt | null;
  diagnostics: DebugDocumentDiagnostics;
  llm: DebugLlm;
};

export type FailureType =
  | "RETRIEVAL_NO_RECALL"
  | "RETRIEVAL_LOW_RANK"
  | "CHUNK_INCOMPLETE"
  | "CONTEXT_MISSING"
  | "PROMPT_SELECTION_WRONG"
  | "GENERATION_WRONG"
  | "HALLUCINATION"
  | "OUTDATED_DOCUMENT"
  | "AMBIGUOUS_QUESTION"
  | "UX_BAD_FORMAT"
  | "LOW_CONFIDENCE_RETRIEVAL"
  | "LLM_ERROR";

export type FailureStatus = "OPEN" | "ANALYZING" | "FIXED" | "WONT_FIX";

export type EvalCaseType = "CORE_RULE" | "FREQUENT_QUERY" | "EDGE_CASE" | "FAILURE_REGRESSION";

export type EvalCaseStatus = "DRAFT" | "ACTIVE" | "INACTIVE" | "REJECTED";

export type CreateFailureCaseRequest = {
  primary_failure_type: FailureType;
  status: FailureStatus;
  priority: number;
  analysis_note?: string | null;
  fix_plan?: string | null;
  source_reason?: string | null;
};

export type FailureCase = {
  id: number;
  query_log_id: number | null;
  source_type: "USER_FEEDBACK" | "MANUAL_DEBUG" | "EVAL_RUN" | "AUTO_RULE";
  source_ref_id: number | null;
  source_reason: string | null;
  primary_failure_type: FailureType | null;
  analysis_note: string | null;
  fix_plan: string | null;
  status: FailureStatus;
  priority: number;
  created_at: string;
  updated_at: string;
  fixed_at: string | null;
};

export type CreateEvalCaseRequest = {
  question?: string | null;
  expected_answer?: string | null;
  case_type: EvalCaseType;
  status: EvalCaseStatus;
  priority: number;
  review_note?: string | null;
};

export type EvalCase = {
  id: number;
  question: string;
  expected_answer: string | null;
  case_type: EvalCaseType;
  status: EvalCaseStatus;
  priority: number;
  created_from: "MANUAL" | "DOCUMENT_GENERATED" | "QUERY_LOG" | "USER_FEEDBACK" | "FAILURE_CASE" | "CSV_IMPORT";
  source_ref_id: number | null;
  created_by: string | null;
  reviewed_by: string | null;
  review_note: string | null;
  reviewed_at: string | null;
  activated_at: string | null;
  created_at: string;
  updated_at: string;
};

export type SynonymGroupStatus = "ACTIVE" | "INACTIVE";

export type SynonymTermType = "CANONICAL" | "SYNONYM";

export type SynonymTermStatus = "ACTIVE" | "INACTIVE";

export type SynonymTerm = {
  id: number;
  group_id: number;
  term: string;
  term_type: SynonymTermType;
  language: string;
  weight: number;
  status: SynonymTermStatus;
  created_at: string;
  updated_at: string;
};

export type SynonymGroup = {
  id: number;
  name: string;
  description: string | null;
  status: SynonymGroupStatus;
  terms: SynonymTerm[];
  created_at: string;
  updated_at: string;
};

export type SynonymGroupListResponse = {
  items: SynonymGroup[];
};

export type CreateSynonymTermRequest = {
  term: string;
  term_type?: SynonymTermType;
  language?: string;
  weight?: number;
  status?: SynonymTermStatus;
};

export type CreateSynonymGroupRequest = {
  name: string;
  description?: string | null;
  status?: SynonymGroupStatus;
  terms?: CreateSynonymTermRequest[];
};

export type UpdateSynonymGroupRequest = {
  name?: string;
  description?: string | null;
  status?: SynonymGroupStatus;
};

export type UpdateSynonymTermRequest = {
  term?: string;
  term_type?: SynonymTermType;
  language?: string;
  weight?: number;
  status?: SynonymTermStatus;
};

export type NormalizeQueryResponse = {
  original_text: string;
  normalized_text: string;
  expanded_text: string;
  applied_synonym_groups: string[];
};
