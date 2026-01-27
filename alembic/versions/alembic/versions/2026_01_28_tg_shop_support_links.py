"""telegram_shop: support links settings

Revision ID: tg_shop_support_links_0128d
Revises: tg_shop_order_items_sku_0128c
Create Date: 2026-01-28
"""

from __future__ import annotations

from alembic import op

revision = "tg_shop_support_links_0128d"
down_revision = "tg_shop_order_items_sku_0128c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS telegram_shop_support_links (
            tenant_id TEXT NOT NULL,
            key TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL DEFAULT '',
            enabled INT NOT NULL DEFAULT 1,
            sort INT NOT NULL DEFAULT 0,
            PRIMARY KEY (tenant_id, key)
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tgshop_support_links_tenant_enabled
        ON telegram_shop_support_links (tenant_id, enabled, sort);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_tgshop_support_links_tenant_enabled;")
    op.execute("DROP TABLE IF EXISTS telegram_shop_support_links;")