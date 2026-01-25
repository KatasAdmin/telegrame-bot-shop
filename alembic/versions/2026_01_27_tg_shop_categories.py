"""telegram_shop: categories table

Revision ID: tg_shop_categories_0127
Revises: tg_shop_hits_promos_0126a
Create Date: 2026-01-27
"""
from __future__ import annotations

from alembic import op

revision = "tg_shop_categories_0127"
down_revision = "tg_shop_hits_promos_0126a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL safe SQL (IF NOT EXISTS) — щоб не ловити "already exists"
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS telegram_shop_categories (
            id SERIAL PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            name TEXT NOT NULL,
            sort INTEGER NOT NULL DEFAULT 0,
            created_ts INTEGER NOT NULL DEFAULT 0
        );
        """
    )

    # унікальність назви в межах tenant
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_tg_shop_categories_tenant_name'
            ) THEN
                ALTER TABLE telegram_shop_categories
                ADD CONSTRAINT uq_tg_shop_categories_tenant_name UNIQUE (tenant_id, name);
            END IF;
        END $$;
        """
    )

    # індекси
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_tg_shop_categories_tenant ON telegram_shop_categories (tenant_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_tg_shop_categories_tenant_sort ON telegram_shop_categories (tenant_id, sort, id);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_tg_shop_categories_tenant_sort;")
    op.execute("DROP INDEX IF EXISTS idx_tg_shop_categories_tenant;")
    op.execute("ALTER TABLE telegram_shop_categories DROP CONSTRAINT IF EXISTS uq_tg_shop_categories_tenant_name;")
    op.execute("DROP TABLE IF EXISTS telegram_shop_categories;")