"""product_key + warnings + trial usage

Revision ID: 0006_trial_warnings_product_key
Revises: 0005_tenant_display_name
Create Date: 2026-01-18
"""
from alembic import op
import sqlalchemy as sa

# ❗️ЦЕ КРИТИЧНО — саме цей ID Alembic зараз шукає
revision = "0006_trial_warnings_product_key"
down_revision = "0005_tenant_display_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # tenants: product key + warning timestamps
    op.add_column(
        "tenants",
        sa.Column("product_key", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("warned_24h_ts", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "tenants",
        sa.Column("warned_3h_ts", sa.BigInteger(), nullable=False, server_default="0"),
    )

    # корисні індекси (безпечно)
    op.create_index("ix_tenants_product_key", "tenants", ["product_key"])
    op.create_index("ix_tenants_paid_until_ts", "tenants", ["paid_until_ts"])
    op.create_index("ix_tenants_status", "tenants", ["status"])

    # trial usage: 1 trial per (owner_user_id, product_key)
    op.create_table(
        "tenant_trial_usage",
        sa.Column("owner_user_id", sa.BigInteger(), nullable=False),
        sa.Column("product_key", sa.String(length=64), nullable=False),
        sa.Column("first_used_ts", sa.BigInteger(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("owner_user_id", "product_key"),
    )
    op.create_index("ix_trial_usage_owner", "tenant_trial_usage", ["owner_user_id"])
    op.create_index("ix_trial_usage_product", "tenant_trial_usage", ["product_key"])


def downgrade() -> None:
    op.drop_index("ix_trial_usage_product", table_name="tenant_trial_usage")
    op.drop_index("ix_trial_usage_owner", table_name="tenant_trial_usage")
    op.drop_table("tenant_trial_usage")

    op.drop_index("ix_tenants_status", table_name="tenants")
    op.drop_index("ix_tenants_paid_until_ts", table_name="tenants")
    op.drop_index("ix_tenants_product_key", table_name="tenants")

    op.drop_column("tenants", "warned_3h_ts")
    op.drop_column("tenants", "warned_24h_ts")
    op.drop_column("tenants", "product_key")