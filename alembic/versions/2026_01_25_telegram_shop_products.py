"""telegram_shop products

Revision ID: 2026_01_25_telegram_shop_products
Revises: add_withdraw_balance_kop
Create Date: 2026-01-25
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "2026_01_25_telegram_shop_products"
down_revision = "add_withdraw_balance_kop"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_shop_products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),

        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("price_kop", sa.Integer(), nullable=False, server_default="0"),

        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),

        # Хіти / Акції
        sa.Column("is_hit", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("promo_price_kop", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("promo_until_ts", sa.Integer(), nullable=False, server_default="0"),

        sa.Column("created_ts", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_index("idx_tg_shop_products_tenant", "telegram_shop_products", ["tenant_id"])
    op.create_index("idx_tg_shop_products_tenant_hit", "telegram_shop_products", ["tenant_id", "is_hit"])
    op.create_index("idx_tg_shop_products_tenant_promo", "telegram_shop_products", ["tenant_id", "promo_until_ts"])


def downgrade() -> None:
    op.drop_index("idx_tg_shop_products_tenant_promo", table_name="telegram_shop_products")
    op.drop_index("idx_tg_shop_products_tenant_hit", table_name="telegram_shop_products")
    op.drop_index("idx_tg_shop_products_tenant", table_name="telegram_shop_products")
    op.drop_table("telegram_shop_products")