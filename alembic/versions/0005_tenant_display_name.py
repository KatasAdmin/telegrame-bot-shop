"""tenant display name

Revision ID: 0005_tenant_display_name
Revises: 0004_tenant_secrets_integrations
Create Date: 2026-01-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_tenant_display_name"
down_revision = "0004_tenant_secrets_integrations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("display_name", sa.String(length=128), nullable=False, server_default="Bot"),
    )


def downgrade() -> None:
    op.drop_column("tenants", "display_name")