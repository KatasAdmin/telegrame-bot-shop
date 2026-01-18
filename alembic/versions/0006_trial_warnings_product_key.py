"""trial usage + product key + warning timestamps

Revision ID: 0006_trial_warnings_product_key
Revises: 0005_tenant_display_name
Create Date: 2026-01-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_trial_warnings_product_key"
down_revision = "0005_tenant_display_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # tenants: product_key + warning flags
    op.add_column("tenants", sa.Column("product_key", sa.String(length=32), nullable=True))
    op.add_column("tenants", sa.Column("warned_24h_ts", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("tenants", sa.Column("warned_3h_ts", sa.BigInteger(), nullable=False, server_default="0"))

    # trial usage: 1 trial per user per product
    op.create_table(
        "tenant_trial_usage",
        sa.Column("owner_user_id", sa.BigInteger(), nullable=False),
        sa.Column("product_key", sa.String(length=32), nullable=False),
        sa.Column("first_used_ts", sa.BigInteger(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("owner_user_id", "product_key"),
    )


def downgrade() -> None:
    op.drop_table("tenant_trial_usage")
    op.drop_column("tenants", "warned_3h_ts")
    op.drop_column("tenants", "warned_24h_ts")
    op.drop_column("tenants", "product_key")