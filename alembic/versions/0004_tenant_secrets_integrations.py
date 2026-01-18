"""tenant secrets + integrations

Revision ID: 0004_tenant_secrets_integrations
Revises: 0003_billing_fields
Create Date: 2026-01-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_tenant_secrets_integrations"
down_revision = "0003_billing_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_secrets",
        sa.Column("tenant_id", sa.String(length=32), nullable=False),
        sa.Column("secret_key", sa.String(length=64), nullable=False),
        sa.Column("secret_value", sa.Text(), nullable=False),
        sa.Column("updated_ts", sa.BigInteger(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("tenant_id", "secret_key"),
    )

    op.create_table(
        "tenant_integrations",
        sa.Column("tenant_id", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),  # mono|privat|crypto|...
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("updated_ts", sa.BigInteger(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("tenant_id", "provider"),
    )


def downgrade() -> None:
    op.drop_table("tenant_integrations")
    op.drop_table("tenant_secrets")