"""telegram_shop: add category_id to products

Revision ID: tg_shop_products_catid_0127
Revises: tg_shop_hits_promos_0126a
Create Date: 2026-01-27
"""
from __future__ import annotations

from alembic import op

revision = "tg_shop_products_catid_0127"
down_revision = "tg_shop_hits_promos_0126a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) column (SAFE)
    op.execute("ALTER TABLE telegram_shop_products ADD COLUMN IF NOT EXISTS category_id INTEGER;")

    # 2) index (SAFE)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_tg_shop_products_tenant_category "
        "ON telegram_shop_products (tenant_id, category_id);"
    )

    # 3) FK (не гарантує tenant-match, але корисний; SAFE)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_tg_shop_products_category_id'
            ) THEN
                ALTER TABLE telegram_shop_products
                ADD CONSTRAINT fk_tg_shop_products_category_id
                FOREIGN KEY (category_id) REFERENCES telegram_shop_categories(id)
                ON DELETE SET NULL;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE telegram_shop_products DROP CONSTRAINT IF EXISTS fk_tg_shop_products_category_id;")
    op.execute("DROP INDEX IF EXISTS idx_tg_shop_products_tenant_category;")
    op.execute("ALTER TABLE telegram_shop_products DROP COLUMN IF EXISTS category_id;")