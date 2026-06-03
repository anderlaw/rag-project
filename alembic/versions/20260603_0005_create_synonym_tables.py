"""create synonym tables

Revision ID: 20260603_0005
Revises: 20260603_0004
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa


revision = "20260603_0005"
down_revision = "20260603_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    bigint_pk = sa.BigInteger().with_variant(sa.Integer(), "sqlite")

    if "rag_synonym_groups" not in existing_tables:
        op.create_table(
            "rag_synonym_groups",
            sa.Column("id", bigint_pk, primary_key=True, autoincrement=True),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("description", sa.Text()),
            sa.Column("status", sa.Text(), nullable=False, server_default="ACTIVE"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint(
                "status IN ('ACTIVE', 'INACTIVE')",
                name="chk_rag_synonym_groups_status",
            ),
        )
        op.create_index("idx_rag_synonym_groups_status", "rag_synonym_groups", ["status"])

    if "rag_synonym_terms" not in existing_tables:
        op.create_table(
            "rag_synonym_terms",
            sa.Column("id", bigint_pk, primary_key=True, autoincrement=True),
            sa.Column("group_id", sa.BigInteger(), nullable=False),
            sa.Column("term", sa.Text(), nullable=False),
            sa.Column("term_type", sa.Text(), nullable=False, server_default="SYNONYM"),
            sa.Column("language", sa.Text(), nullable=False, server_default="mixed"),
            sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
            sa.Column("status", sa.Text(), nullable=False, server_default="ACTIVE"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("group_id", "term", name="uq_rag_synonym_terms_group_term"),
            sa.CheckConstraint(
                "term_type IN ('CANONICAL', 'SYNONYM')",
                name="chk_rag_synonym_terms_type",
            ),
            sa.CheckConstraint(
                "status IN ('ACTIVE', 'INACTIVE')",
                name="chk_rag_synonym_terms_status",
            ),
            sa.CheckConstraint("weight >= 0", name="chk_rag_synonym_terms_weight"),
        )
        op.create_index("idx_rag_synonym_terms_group", "rag_synonym_terms", ["group_id"])
        op.create_index("idx_rag_synonym_terms_status", "rag_synonym_terms", ["status"])

    groups = sa.table(
        "rag_synonym_groups",
        sa.column("id", sa.BigInteger()),
        sa.column("name", sa.Text()),
        sa.column("description", sa.Text()),
        sa.column("status", sa.Text()),
    )
    terms = sa.table(
        "rag_synonym_terms",
        sa.column("id", sa.BigInteger()),
        sa.column("group_id", sa.BigInteger()),
        sa.column("term", sa.Text()),
        sa.column("term_type", sa.Text()),
        sa.column("language", sa.Text()),
        sa.column("weight", sa.Float()),
        sa.column("status", sa.Text()),
    )

    existing_tech_stack = bind.execute(
        sa.text("SELECT id FROM rag_synonym_groups WHERE name = :name"),
        {"name": "技术栈"},
    ).first()
    if existing_tech_stack is None:
        op.bulk_insert(
            groups,
            [
                {
                    "id": 1,
                    "name": "技术栈",
                    "description": "技术栈相关 query 扩展默认词组",
                    "status": "ACTIVE",
                }
            ],
        )
        op.bulk_insert(
            terms,
            [
                {"id": 1, "group_id": 1, "term": "技术栈", "term_type": "CANONICAL", "language": "zh", "weight": 1.0, "status": "ACTIVE"},
                {"id": 2, "group_id": 1, "term": "技术选型", "term_type": "SYNONYM", "language": "zh", "weight": 1.0, "status": "ACTIVE"},
                {"id": 3, "group_id": 1, "term": "技术方案", "term_type": "SYNONYM", "language": "zh", "weight": 1.0, "status": "ACTIVE"},
                {"id": 4, "group_id": 1, "term": "技术框架", "term_type": "SYNONYM", "language": "zh", "weight": 1.0, "status": "ACTIVE"},
                {"id": 5, "group_id": 1, "term": "tech stack", "term_type": "SYNONYM", "language": "en", "weight": 1.0, "status": "ACTIVE"},
            ],
        )

        if bind.dialect.name == "postgresql":
            op.execute(
                "SELECT setval(pg_get_serial_sequence('rag_synonym_groups', 'id'), "
                "(SELECT COALESCE(MAX(id), 1) FROM rag_synonym_groups))"
            )
            op.execute(
                "SELECT setval(pg_get_serial_sequence('rag_synonym_terms', 'id'), "
                "(SELECT COALESCE(MAX(id), 1) FROM rag_synonym_terms))"
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "rag_synonym_terms" in existing_tables:
        op.drop_index("idx_rag_synonym_terms_status", table_name="rag_synonym_terms")
        op.drop_index("idx_rag_synonym_terms_group", table_name="rag_synonym_terms")
        op.drop_table("rag_synonym_terms")

    if "rag_synonym_groups" in existing_tables:
        op.drop_index("idx_rag_synonym_groups_status", table_name="rag_synonym_groups")
        op.drop_table("rag_synonym_groups")
