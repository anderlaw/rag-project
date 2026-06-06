"""add search feedback and result snapshots

Revision ID: 20260606_0006
Revises: 20260603_0005
Create Date: 2026-06-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260606_0006"
down_revision = "20260603_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    bigint_pk = sa.BigInteger().with_variant(sa.Integer(), "sqlite")

    if "rag_query_candidates" in existing_tables:
        existing_columns = {column["name"] for column in inspector.get_columns("rag_query_candidates")}
        for column_name in [
            "result_answer",
            "result_answer_status",
            "result_answer_error",
            "before_context_snapshot",
            "after_context_snapshot",
        ]:
            if column_name not in existing_columns:
                op.add_column("rag_query_candidates", sa.Column(column_name, sa.Text()))

    if "rag_query_feedbacks" not in existing_tables:
        op.create_table(
            "rag_query_feedbacks",
            sa.Column("id", bigint_pk, primary_key=True, autoincrement=True),
            sa.Column("query_log_id", sa.BigInteger(), nullable=False),
            sa.Column("username", sa.Text(), nullable=False),
            sa.Column("role", sa.Text(), nullable=False),
            sa.Column("rating", sa.Text(), nullable=False),
            sa.Column("comment", sa.Text()),
            sa.Column("expected_answer", sa.Text()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint(
                "rating IN ('HELPFUL', 'PARTIALLY_HELPFUL', 'NOT_HELPFUL')",
                name="chk_rag_query_feedbacks_rating",
            ),
        )
        op.create_index("idx_rag_query_feedbacks_query_log", "rag_query_feedbacks", ["query_log_id"])
        op.create_index("idx_rag_query_feedbacks_username", "rag_query_feedbacks", ["username"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "rag_query_feedbacks" in existing_tables:
        op.drop_index("idx_rag_query_feedbacks_username", table_name="rag_query_feedbacks")
        op.drop_index("idx_rag_query_feedbacks_query_log", table_name="rag_query_feedbacks")
        op.drop_table("rag_query_feedbacks")

    if "rag_query_candidates" in existing_tables:
        existing_columns = {column["name"] for column in inspector.get_columns("rag_query_candidates")}
        for column_name in [
            "after_context_snapshot",
            "before_context_snapshot",
            "result_answer_error",
            "result_answer_status",
            "result_answer",
        ]:
            if column_name in existing_columns:
                op.drop_column("rag_query_candidates", column_name)
