"""tg shop payment providers settings

Revision ID: tg_shop_payment_providers_0129p
Revises: tg_shop_order_items_sku_0128c
Create Date: 2026-01-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "tg_shop_payment_providers_0129p"
down_revision = "tg_shop_order_items_sku_0128c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_shop_payment_providers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("value", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("created_ts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("updated_ts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.UniqueConstraint("tenant_id", "key", name="uq_tg_shop_payprov_tenant_key"),
    )
    op.create_index(
        "ix_tg_shop_payprov_tenant",
        "telegram_shop_payment_providers",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tg_shop_payprov_tenant", table_name="telegram_shop_payment_providers")
    op.drop_table("telegram_shop_payment_providers")