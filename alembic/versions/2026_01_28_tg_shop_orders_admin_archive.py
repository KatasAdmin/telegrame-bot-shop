"""telegram_shop: admin orders archive table

Revision ID: tg_shop_orders_admin_archive_0128b
Revises: tg_shop_orders_archive_0128a
Create Date: 2026-01-28
"""
from __future__ import annotations

import time
from alembic import op

revision = "tg_shop_orders_admin_archive_0128b"
down_revision = "tg_alembic_ver_0128"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS telegram_shop_orders_admin_archive (
            tenant_id   TEXT NOT NULL,
            order_id    INT  NOT NULL,
            archived_ts INT  NOT NULL DEFAULT 0,
            PRIMARY KEY (tenant_id, order_id)
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tg_ord_admin_arch_tenant_ts
        ON telegram_shop_orders_admin_archive (tenant_id, archived_ts DESC);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_tg_ord_admin_arch_tenant_ts;")
    op.execute("DROP TABLE IF EXISTS telegram_shop_orders_admin_archive;")