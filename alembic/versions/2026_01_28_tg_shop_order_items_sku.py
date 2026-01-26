"""telegram_shop: add sku snapshot to order items

Revision ID: tg_shop_order_items_sku_0128c
Revises: tg_shop_orders_admin_archive_0128b
Create Date: 2026-01-28
"""
from __future__ import annotations

from alembic import op

revision = "tg_shop_order_items_sku_0128c"
down_revision = "tg_shop_orders_admin_archive_0128b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE telegram_shop_order_items ADD COLUMN IF NOT EXISTS sku TEXT;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tg_order_items_oid ON telegram_shop_order_items (order_id);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_tg_order_items_oid;")
    op.execute("ALTER TABLE telegram_shop_order_items DROP COLUMN IF EXISTS sku;")