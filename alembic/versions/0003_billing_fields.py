"""billing fields

Revision ID: 0003_billing_fields
Revises: 0002_owner_user_id_bigint
Create Date: 2026-01-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_billing_fields"
down_revision = "0002_owner_user_id_bigint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("plan_key", sa.String(length=32), nullable=False, server_default="free"),
    )
    op.add_column(
        "tenants",
        sa.Column("paid_until_ts", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "tenants",
        sa.Column("paused_reason", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "paused_reason")
    op.drop_column("tenants", "paid_until_ts")
    op.drop_column("tenants", "plan_key")