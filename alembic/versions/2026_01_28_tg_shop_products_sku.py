"""telegram_shop: add sku to products

Revision ID: tg_shop_products_sku_0128
Revises: merge_tg_cats_catid_0127m
Create Date: 2026-01-28
"""
from __future__ import annotations

from alembic import op


revision = "tg_shop_products_sku_0128"
down_revision = "merge_tg_cats_catid_0127m"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) column (SAFE)
    op.execute("ALTER TABLE telegram_shop_products ADD COLUMN IF NOT EXISTS sku TEXT;")

    # 2) індекс під пошук/фільтр (SAFE)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_tg_shop_products_tenant_sku "
        "ON telegram_shop_products (tenant_id, sku);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_tg_shop_products_tenant_sku;")
    op.execute("ALTER TABLE telegram_shop_products DROP COLUMN IF EXISTS sku;")