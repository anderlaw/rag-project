"""add query candidate location fields

Revision ID: 20260603_0004
Revises: 20260603_0003
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa


revision = "20260603_0004"
down_revision = "20260603_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("rag_query_candidates")}

    if "start_char" not in existing_columns:
        op.add_column("rag_query_candidates", sa.Column("start_char", sa.Integer()))
    if "end_char" not in existing_columns:
        op.add_column("rag_query_candidates", sa.Column("end_char", sa.Integer()))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("rag_query_candidates")}

    if "end_char" in existing_columns:
        op.drop_column("rag_query_candidates", "end_char")
    if "start_char" in existing_columns:
        op.drop_column("rag_query_candidates", "start_char")
