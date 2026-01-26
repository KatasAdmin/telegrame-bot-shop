"""telegram_shop: favorites table

Revision ID: tg_shop_favorites_0128
Revises: tg_shop_products_sku_0128
Create Date: 2026-01-28
"""
from __future__ import annotations

from alembic import op

revision = "tg_shop_favorites_0128"
down_revision = "tg_shop_products_sku_0128"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS telegram_shop_favorites (
            tenant_id  TEXT   NOT NULL,
            user_id    BIGINT NOT NULL,
            product_id INT    NOT NULL,
            created_ts INT    NOT NULL DEFAULT 0,
            PRIMARY KEY (tenant_id, user_id, product_id)
        );
        """
    )

    # щоб швидко діставати "перший/список" по користувачу
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tg_fav_tenant_user_ts
        ON telegram_shop_favorites (tenant_id, user_id, created_ts DESC);
        """
    )

    # інколи корисно (не обовʼязково, але норм)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tg_fav_tenant_product
        ON telegram_shop_favorites (tenant_id, product_id);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_tg_fav_tenant_user_ts;")
    op.execute("DROP INDEX IF EXISTS idx_tg_fav_tenant_product;")
    op.execute("DROP TABLE IF EXISTS telegram_shop_favorites;")