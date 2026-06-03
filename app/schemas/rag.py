from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class FailureSourceType(StrEnum):
    USER_FEEDBACK = "USER_FEEDBACK"
    MANUAL_DEBUG = "MANUAL_DEBUG"
    EVAL_RUN = "EVAL_RUN"
    AUTO_RULE = "AUTO_RULE"


class FailureType(StrEnum):
    RETRIEVAL_NO_RECALL = "RETRIEVAL_NO_RECALL"
    RETRIEVAL_LOW_RANK = "RETRIEVAL_LOW_RANK"
    CHUNK_INCOMPLETE = "CHUNK_INCOMPLETE"
    CONTEXT_MISSING = "CONTEXT_MISSING"
    PROMPT_SELECTION_WRONG = "PROMPT_SELECTION_WRONG"
    GENERATION_WRONG = "GENERATION_WRONG"
    HALLUCINATION = "HALLUCINATION"
    OUTDATED_DOCUMENT = "OUTDATED_DOCUMENT"
    AMBIGUOUS_QUESTION = "AMBIGUOUS_QUESTION"
    UX_BAD_FORMAT = "UX_BAD_FORMAT"
    LOW_CONFIDENCE_RETRIEVAL = "LOW_CONFIDENCE_RETRIEVAL"
    LLM_ERROR = "LLM_ERROR"


class FailureStatus(StrEnum):
    OPEN = "OPEN"
    ANALYZING = "ANALYZING"
    FIXED = "FIXED"
    WONT_FIX = "WONT_FIX"


class EvalCaseType(StrEnum):
    CORE_RULE = "CORE_RULE"
    FREQUENT_QUERY = "FREQUENT_QUERY"
    EDGE_CASE = "EDGE_CASE"
    FAILURE_REGRESSION = "FAILURE_REGRESSION"


class EvalCaseStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    REJECTED = "REJECTED"


class EvalCaseCreatedFrom(StrEnum):
    MANUAL = "MANUAL"
    DOCUMENT_GENERATED = "DOCUMENT_GENERATED"
    QUERY_LOG = "QUERY_LOG"
    USER_FEEDBACK = "USER_FEEDBACK"
    FAILURE_CASE = "FAILURE_CASE"
    CSV_IMPORT = "CSV_IMPORT"


class DebugQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    search_profile_id: int | None = None
    use_llm: bool = False
    vector_top_k: int = Field(default=20, ge=0, le=100)
    keyword_top_k: int = Field(default=20, ge=0, le=100)
    trgm_top_k: int = Field(default=20, ge=0, le=100)
    final_top_k: int = Field(default=5, ge=0, le=50)
    vector_weight: float = Field(default=0.65, ge=0, le=1)
    keyword_weight: float = Field(default=0.25, ge=0, le=1)
    trgm_weight: float = Field(default=0.10, ge=0, le=1)
    min_final_score: float = Field(default=0.55, ge=0, le=1)


class DebugSearchProfileResponse(BaseModel):
    id: int | None = None
    name: str
    mode: str
    vector_top_k: int
    keyword_top_k: int
    trgm_top_k: int
    final_top_k: int
    vector_weight: float
    keyword_weight: float
    trgm_weight: float
    min_final_score: float


class DebugCandidateResponse(BaseModel):
    rank: int
    chunk_id: int
    document_id: int
    document_version_id: int
    document_name: str
    section_title: str | None = None
    heading_path: str | None = None
    parent_chunk_id: int | None = None
    chunk_index: int
    child_index: int | None = None
    start_char: int | None = None
    end_char: int | None = None
    page_number: int | None = None
    vector_score: float
    keyword_score: float
    trgm_score: float
    final_score: float
    selected_for_prompt: bool
    content_preview: str
    content: str
    content_with_context: str | None = None


class DebugPromptResponse(BaseModel):
    version: str
    text: str


class DebugLlmResponse(BaseModel):
    used: bool
    model: str | None = None
    latency_ms: int | None = None
    answer: str | None = None
    error: str | None = None


class DebugDocumentStatusMatchResponse(BaseModel):
    document_id: int
    name: str
    status: str
    current_version_id: int | None = None
    version_status: str | None = None
    chunk_count: int | None = None
    match_reason: str


class DebugDocumentDiagnosticsResponse(BaseModel):
    active_document_count: int
    searchable_child_chunk_count: int
    inactive_related_documents: list[DebugDocumentStatusMatchResponse] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DebugQueryResponse(BaseModel):
    query_log_id: int | None = None
    question: str
    search_profile: DebugSearchProfileResponse
    candidates: list[DebugCandidateResponse]
    selected_chunks: list[DebugCandidateResponse]
    prompt: DebugPromptResponse | None = None
    diagnostics: DebugDocumentDiagnosticsResponse
    llm: DebugLlmResponse


class QueryLogDetailResponse(BaseModel):
    id: int
    question: str
    search_mode: str
    use_llm: bool
    created_at: datetime
    search_profile: DebugSearchProfileResponse
    model_config_snapshot: dict | None = None
    search_latency_ms: int | None = None
    llm_latency_ms: int | None = None
    total_latency_ms: int | None = None
    candidates: list[DebugCandidateResponse]
    selected_chunks: list[DebugCandidateResponse]
    prompt: DebugPromptResponse | None = None
    diagnostics: DebugDocumentDiagnosticsResponse
    llm: DebugLlmResponse


class CreateFailureCaseFromQueryLogRequest(BaseModel):
    primary_failure_type: FailureType
    status: FailureStatus = FailureStatus.OPEN
    priority: int = Field(default=3, ge=1, le=5)
    analysis_note: str | None = None
    fix_plan: str | None = None
    source_reason: str | None = None


class FailureCaseResponse(BaseModel):
    id: int
    query_log_id: int | None = None
    source_type: FailureSourceType
    source_ref_id: int | None = None
    source_reason: str | None = None
    primary_failure_type: FailureType | None = None
    analysis_note: str | None = None
    fix_plan: str | None = None
    status: FailureStatus
    priority: int
    created_at: datetime
    updated_at: datetime
    fixed_at: datetime | None = None

    model_config = {"from_attributes": True}


class CreateEvalCaseFromQueryLogRequest(BaseModel):
    question: str | None = Field(default=None, min_length=1, max_length=4000)
    expected_answer: str | None = None
    case_type: EvalCaseType = EvalCaseType.FAILURE_REGRESSION
    status: EvalCaseStatus = EvalCaseStatus.DRAFT
    priority: int = Field(default=3, ge=1, le=5)
    review_note: str | None = None


class EvalCaseResponse(BaseModel):
    id: int
    question: str
    expected_answer: str | None = None
    case_type: EvalCaseType
    status: EvalCaseStatus
    priority: int
    created_from: EvalCaseCreatedFrom
    source_ref_id: int | None = None
    created_by: str | None = None
    reviewed_by: str | None = None
    review_note: str | None = None
    reviewed_at: datetime | None = None
    activated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
