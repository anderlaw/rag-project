"""create failure and eval case tables

Revision ID: 20260603_0003
Revises: 20260602_0002
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260603_0003"
down_revision = "20260602_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    is_postgres = bind.dialect.name == "postgresql"
    bigint_pk = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
    json_type = postgresql.JSONB() if is_postgres else sa.JSON()

    if "rag_failure_cases" not in existing_tables:
        op.create_table(
            "rag_failure_cases",
            sa.Column("id", bigint_pk, primary_key=True, autoincrement=True),
            sa.Column("query_log_id", sa.BigInteger()),
            sa.Column("source_type", sa.Text(), nullable=False),
            sa.Column("source_ref_id", sa.BigInteger()),
            sa.Column("source_reason", sa.Text()),
            sa.Column("source_payload", json_type),
            sa.Column("primary_failure_type", sa.Text()),
            sa.Column("analysis_note", sa.Text()),
            sa.Column("fix_plan", sa.Text()),
            sa.Column("status", sa.Text(), nullable=False, server_default="OPEN"),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("fixed_at", sa.DateTime()),
            sa.CheckConstraint(
                "source_type IN ('USER_FEEDBACK', 'MANUAL_DEBUG', 'EVAL_RUN', 'AUTO_RULE')",
                name="chk_rag_failure_cases_source_type",
            ),
            sa.CheckConstraint(
                "status IN ('OPEN', 'ANALYZING', 'FIXED', 'WONT_FIX')",
                name="chk_rag_failure_cases_status",
            ),
            sa.CheckConstraint("priority >= 1 AND priority <= 5", name="chk_rag_failure_cases_priority"),
        )
        op.create_index("idx_rag_failure_cases_query_log", "rag_failure_cases", ["query_log_id"])
        op.create_index("idx_rag_failure_cases_status", "rag_failure_cases", ["status"])

    if "rag_eval_cases" not in existing_tables:
        op.create_table(
            "rag_eval_cases",
            sa.Column("id", bigint_pk, primary_key=True, autoincrement=True),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("expected_answer", sa.Text()),
            sa.Column("case_type", sa.Text(), nullable=False, server_default="CORE_RULE"),
            sa.Column("status", sa.Text(), nullable=False, server_default="DRAFT"),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("created_from", sa.Text(), nullable=False, server_default="MANUAL"),
            sa.Column("source_ref_id", sa.BigInteger()),
            sa.Column("source_payload", json_type),
            sa.Column("created_by", sa.Text()),
            sa.Column("reviewed_by", sa.Text()),
            sa.Column("review_note", sa.Text()),
            sa.Column("reviewed_at", sa.DateTime()),
            sa.Column("activated_at", sa.DateTime()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint(
                "case_type IN ('CORE_RULE', 'FREQUENT_QUERY', 'EDGE_CASE', 'FAILURE_REGRESSION')",
                name="chk_rag_eval_cases_case_type",
            ),
            sa.CheckConstraint(
                "status IN ('DRAFT', 'ACTIVE', 'INACTIVE', 'REJECTED')",
                name="chk_rag_eval_cases_status",
            ),
            sa.CheckConstraint(
                "created_from IN ('MANUAL', 'DOCUMENT_GENERATED', 'QUERY_LOG', 'USER_FEEDBACK', 'FAILURE_CASE', 'CSV_IMPORT')",
                name="chk_rag_eval_cases_created_from",
            ),
            sa.CheckConstraint("priority >= 1 AND priority <= 5", name="chk_rag_eval_cases_priority"),
        )
        op.create_index("idx_rag_eval_cases_status", "rag_eval_cases", ["status"])
        op.create_index("idx_rag_eval_cases_created_from", "rag_eval_cases", ["created_from"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "rag_eval_cases" in existing_tables:
        op.drop_index("idx_rag_eval_cases_created_from", table_name="rag_eval_cases")
        op.drop_index("idx_rag_eval_cases_status", table_name="rag_eval_cases")
        op.drop_table("rag_eval_cases")

    if "rag_failure_cases" in existing_tables:
        op.drop_index("idx_rag_failure_cases_status", table_name="rag_failure_cases")
        op.drop_index("idx_rag_failure_cases_query_log", table_name="rag_failure_cases")
        op.drop_table("rag_failure_cases")
