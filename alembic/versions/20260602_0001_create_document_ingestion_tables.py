"""create document ingestion tables

Revision ID: 20260602_0001
Revises:
Create Date: 2026-06-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

try:
    from pgvector.sqlalchemy import Vector
except Exception:  # pragma: no cover
    Vector = None


revision = "20260602_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    if is_postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    bigint_pk = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
    embedding_type = Vector(1536) if is_postgres and Vector is not None else sa.JSON()
    json_type = postgresql.JSONB() if is_postgres else sa.JSON()

    op.create_table(
        "rag_documents",
        sa.Column("id", bigint_pk, primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("file_type", sa.Text()),
        sa.Column("file_size", sa.BigInteger()),
        sa.Column("current_version_id", sa.BigInteger()),
        sa.Column("status", sa.Text(), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "rag_document_versions",
        sa.Column("id", bigint_pk, primary_key=True, autoincrement=True),
        sa.Column("document_id", sa.BigInteger(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("file_hash", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.Text()),
        sa.Column("storage_key", sa.Text()),
        sa.Column("parser_version", sa.Text()),
        sa.Column("parser_config_snapshot", json_type),
        sa.Column("chunk_strategy_name", sa.Text()),
        sa.Column("chunk_config_snapshot", json_type),
        sa.Column("status", sa.Text(), nullable=False, server_default="PROCESSING"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime()),
        sa.UniqueConstraint("document_id", "version_no", name="uq_document_version_no"),
        sa.UniqueConstraint("document_id", "id", name="uq_document_version_id"),
    )
    op.create_index("idx_rag_document_versions_document", "rag_document_versions", ["document_id"])

    op.create_table(
        "rag_chunks",
        sa.Column("id", bigint_pk, primary_key=True, autoincrement=True),
        sa.Column("document_id", sa.BigInteger(), nullable=False),
        sa.Column("document_version_id", sa.BigInteger(), nullable=False),
        sa.Column("chunk_type", sa.Text(), nullable=False),
        sa.Column("parent_chunk_id", sa.BigInteger()),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("child_index", sa.Integer()),
        sa.Column("heading_path", sa.Text()),
        sa.Column("section_title", sa.Text()),
        sa.Column("start_char", sa.Integer()),
        sa.Column("end_char", sa.Integer()),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_with_context", sa.Text()),
        sa.Column("search_text", sa.Text()),
        sa.Column("search_tsv", sa.Text()),
        sa.Column("embedding", embedding_type),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_rag_chunks_document_version", "rag_chunks", ["document_version_id"])
    op.create_index("idx_rag_chunks_document_chunk_type", "rag_chunks", ["document_id", "chunk_type"])
    op.create_index("idx_rag_chunks_parent", "rag_chunks", ["parent_chunk_id"])


def downgrade() -> None:
    op.drop_index("idx_rag_chunks_parent", table_name="rag_chunks")
    op.drop_index("idx_rag_chunks_document_chunk_type", table_name="rag_chunks")
    op.drop_index("idx_rag_chunks_document_version", table_name="rag_chunks")
    op.drop_table("rag_chunks")
    op.drop_index("idx_rag_document_versions_document", table_name="rag_document_versions")
    op.drop_table("rag_document_versions")
    op.drop_table("rag_documents")
