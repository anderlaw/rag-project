"""create query log tables

Revision ID: 20260602_0002
Revises: 20260602_0001
Create Date: 2026-06-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260602_0002"
down_revision = "20260602_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    bigint_pk = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
    json_type = postgresql.JSONB() if is_postgres else sa.JSON()

    op.create_table(
        "rag_query_logs",
        sa.Column("id", bigint_pk, primary_key=True, autoincrement=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("search_mode", sa.Text(), nullable=False),
        sa.Column("use_llm", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("search_profile_id", sa.BigInteger()),
        sa.Column("search_profile_snapshot", json_type),
        sa.Column("model_config_snapshot", json_type),
        sa.Column("answer_prompt_version", sa.Text()),
        sa.Column("top_k", sa.Integer()),
        sa.Column("final_top_k", sa.Integer()),
        sa.Column("embedding_model", sa.Text()),
        sa.Column("llm_model", sa.Text()),
        sa.Column("answer_prompt_text", sa.Text()),
        sa.Column("answer", sa.Text()),
        sa.Column("max_score", sa.Float()),
        sa.Column("min_score", sa.Float()),
        sa.Column("search_latency_ms", sa.Integer()),
        sa.Column("llm_latency_ms", sa.Integer()),
        sa.Column("total_latency_ms", sa.Integer()),
        sa.Column("llm_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_rag_query_logs_created_at", "rag_query_logs", ["created_at"])
    op.create_index("idx_rag_query_logs_search_mode", "rag_query_logs", ["search_mode"])

    op.create_table(
        "rag_query_candidates",
        sa.Column("id", bigint_pk, primary_key=True, autoincrement=True),
        sa.Column("query_log_id", sa.BigInteger(), nullable=False),
        sa.Column("chunk_id", sa.BigInteger(), nullable=False),
        sa.Column("parent_chunk_id", sa.BigInteger()),
        sa.Column("document_id", sa.BigInteger(), nullable=False),
        sa.Column("document_version_id", sa.BigInteger(), nullable=False),
        sa.Column("document_name", sa.Text(), nullable=False),
        sa.Column("section_title", sa.Text()),
        sa.Column("heading_path", sa.Text()),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("child_index", sa.Integer()),
        sa.Column("vector_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("keyword_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("trgm_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("final_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("selected_for_prompt", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("content_preview", sa.Text(), nullable=False),
        sa.Column("content_snapshot", sa.Text(), nullable=False),
        sa.Column("content_with_context_snapshot", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_rag_query_candidates_query_log", "rag_query_candidates", ["query_log_id"])
    op.create_index("idx_rag_query_candidates_chunk", "rag_query_candidates", ["chunk_id"])


def downgrade() -> None:
    op.drop_index("idx_rag_query_candidates_chunk", table_name="rag_query_candidates")
    op.drop_index("idx_rag_query_candidates_query_log", table_name="rag_query_candidates")
    op.drop_table("rag_query_candidates")
    op.drop_index("idx_rag_query_logs_search_mode", table_name="rag_query_logs")
    op.drop_index("idx_rag_query_logs_created_at", table_name="rag_query_logs")
    op.drop_table("rag_query_logs")
