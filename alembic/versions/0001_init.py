"""init

Revision ID: 0001_init
Revises:
Create Date: 2026-01-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("owner_user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("bot_token", sa.String(length=256), nullable=False),
        sa.Column("secret", sa.String(length=128), nullable=False, index=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_ts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_tenants_owner_user_id", "tenants", ["owner_user_id"])

    op.create_table(
        "tenant_modules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=32), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("module_key", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_tenant_modules_tenant_id", "tenant_modules", ["tenant_id"])
    op.create_unique_constraint("uq_tenant_module", "tenant_modules", ["tenant_id", "module_key"])


def downgrade() -> None:
    op.drop_constraint("uq_tenant_module", "tenant_modules", type_="unique")
    op.drop_index("ix_tenant_modules_tenant_id", table_name="tenant_modules")
    op.drop_table("tenant_modules")

    op.drop_index("ix_tenants_owner_user_id", table_name="tenants")
    op.drop_table("tenants")