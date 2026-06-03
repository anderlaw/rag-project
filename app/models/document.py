from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Float, Index, Integer, JSON, Text, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.core.database import Base

try:
    from pgvector.sqlalchemy import Vector
except Exception:  # pragma: no cover - only used if pgvector is unavailable.
    Vector = None


BigIntPk = BigInteger().with_variant(Integer, "sqlite")
JsonDict = JSON().with_variant(postgresql.JSONB(), "postgresql")


class EmbeddingVector(TypeDecorator):
    impl = JSON
    cache_ok = True

    def __init__(self, dimensions: int = 1536) -> None:
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql" and Vector is not None:
            return dialect.type_descriptor(Vector(self.dimensions))
        return dialect.type_descriptor(JSON())


class RagDocument(Base):
    __tablename__ = "rag_documents"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str | None] = mapped_column(Text)
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    current_version_id: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class RagDocumentVersion(Base):
    __tablename__ = "rag_document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_no", name="uq_document_version_no"),
        UniqueConstraint("document_id", "id", name="uq_document_version_id"),
        Index("idx_rag_document_versions_document", "document_id"),
    )

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    file_hash: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str | None] = mapped_column(Text)
    storage_key: Mapped[str | None] = mapped_column(Text)
    parser_version: Mapped[str | None] = mapped_column(Text)
    parser_config_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JsonDict)
    chunk_strategy_name: Mapped[str | None] = mapped_column(Text)
    chunk_config_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JsonDict)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="PROCESSING")
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)


class RagChunk(Base):
    __tablename__ = "rag_chunks"
    __table_args__ = (
        Index("idx_rag_chunks_document_version", "document_version_id"),
        Index("idx_rag_chunks_document_chunk_type", "document_id", "chunk_type"),
        Index("idx_rag_chunks_parent", "parent_chunk_id"),
    )

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    document_version_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chunk_type: Mapped[str] = mapped_column(Text, nullable=False)
    parent_chunk_id: Mapped[int | None] = mapped_column(BigInteger)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    child_index: Mapped[int | None] = mapped_column(Integer)
    heading_path: Mapped[str | None] = mapped_column(Text)
    section_title: Mapped[str | None] = mapped_column(Text)
    start_char: Mapped[int | None] = mapped_column(Integer)
    end_char: Mapped[int | None] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_with_context: Mapped[str | None] = mapped_column(Text)
    search_text: Mapped[str | None] = mapped_column(Text)
    search_tsv: Mapped[str | None] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(EmbeddingVector())
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class RagQueryLog(Base):
    __tablename__ = "rag_query_logs"
    __table_args__ = (
        Index("idx_rag_query_logs_created_at", "created_at"),
        Index("idx_rag_query_logs_search_mode", "search_mode"),
    )

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    search_mode: Mapped[str] = mapped_column(Text, nullable=False)
    use_llm: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    search_profile_id: Mapped[int | None] = mapped_column(BigInteger)
    search_profile_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JsonDict)
    model_config_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JsonDict)
    answer_prompt_version: Mapped[str | None] = mapped_column(Text)
    top_k: Mapped[int | None] = mapped_column(Integer)
    final_top_k: Mapped[int | None] = mapped_column(Integer)
    embedding_model: Mapped[str | None] = mapped_column(Text)
    llm_model: Mapped[str | None] = mapped_column(Text)
    answer_prompt_text: Mapped[str | None] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text)
    max_score: Mapped[float | None] = mapped_column(Float)
    min_score: Mapped[float | None] = mapped_column(Float)
    search_latency_ms: Mapped[int | None] = mapped_column(Integer)
    llm_latency_ms: Mapped[int | None] = mapped_column(Integer)
    total_latency_ms: Mapped[int | None] = mapped_column(Integer)
    llm_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class RagQueryCandidate(Base):
    __tablename__ = "rag_query_candidates"
    __table_args__ = (
        Index("idx_rag_query_candidates_query_log", "query_log_id"),
        Index("idx_rag_query_candidates_chunk", "chunk_id"),
    )

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    query_log_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chunk_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    parent_chunk_id: Mapped[int | None] = mapped_column(BigInteger)
    document_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    document_version_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    document_name: Mapped[str] = mapped_column(Text, nullable=False)
    section_title: Mapped[str | None] = mapped_column(Text)
    heading_path: Mapped[str | None] = mapped_column(Text)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    child_index: Mapped[int | None] = mapped_column(Integer)
    start_char: Mapped[int | None] = mapped_column(Integer)
    end_char: Mapped[int | None] = mapped_column(Integer)
    vector_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    keyword_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    trgm_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    final_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    selected_for_prompt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    content_preview: Mapped[str] = mapped_column(Text, nullable=False)
    content_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    content_with_context_snapshot: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class RagFailureCase(Base):
    __tablename__ = "rag_failure_cases"
    __table_args__ = (
        CheckConstraint("source_type IN ('USER_FEEDBACK', 'MANUAL_DEBUG', 'EVAL_RUN', 'AUTO_RULE')", name="chk_rag_failure_cases_source_type"),
        CheckConstraint(
            "status IN ('OPEN', 'ANALYZING', 'FIXED', 'WONT_FIX')",
            name="chk_rag_failure_cases_status",
        ),
        CheckConstraint("priority >= 1 AND priority <= 5", name="chk_rag_failure_cases_priority"),
        Index("idx_rag_failure_cases_query_log", "query_log_id"),
        Index("idx_rag_failure_cases_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    query_log_id: Mapped[int | None] = mapped_column(BigInteger)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref_id: Mapped[int | None] = mapped_column(BigInteger)
    source_reason: Mapped[str | None] = mapped_column(Text)
    source_payload: Mapped[dict[str, Any] | None] = mapped_column(JsonDict)
    primary_failure_type: Mapped[str | None] = mapped_column(Text)
    analysis_note: Mapped[str | None] = mapped_column(Text)
    fix_plan: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="OPEN")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    fixed_at: Mapped[datetime | None] = mapped_column(DateTime)


class RagEvalCase(Base):
    __tablename__ = "rag_eval_cases"
    __table_args__ = (
        CheckConstraint(
            "case_type IN ('CORE_RULE', 'FREQUENT_QUERY', 'EDGE_CASE', 'FAILURE_REGRESSION')",
            name="chk_rag_eval_cases_case_type",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'INACTIVE', 'REJECTED')",
            name="chk_rag_eval_cases_status",
        ),
        CheckConstraint(
            "created_from IN ('MANUAL', 'DOCUMENT_GENERATED', 'QUERY_LOG', 'USER_FEEDBACK', 'FAILURE_CASE', 'CSV_IMPORT')",
            name="chk_rag_eval_cases_created_from",
        ),
        CheckConstraint("priority >= 1 AND priority <= 5", name="chk_rag_eval_cases_priority"),
        Index("idx_rag_eval_cases_status", "status"),
        Index("idx_rag_eval_cases_created_from", "created_from"),
    )

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected_answer: Mapped[str | None] = mapped_column(Text)
    case_type: Mapped[str] = mapped_column(Text, nullable=False, default="CORE_RULE")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="DRAFT")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    created_from: Mapped[str] = mapped_column(Text, nullable=False, default="MANUAL")
    source_ref_id: Mapped[int | None] = mapped_column(BigInteger)
    source_payload: Mapped[dict[str, Any] | None] = mapped_column(JsonDict)
    created_by: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[str | None] = mapped_column(Text)
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
