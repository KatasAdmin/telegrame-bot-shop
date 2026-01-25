"""telegram_shop: categories + products.category_id

Revision ID: tg_shop_categories_0127
Revises: tg_shop_hits_promos_0126a
Create Date: 2026-01-27
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "tg_shop_categories_0127"
down_revision = "tg_shop_hits_promos_0126a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) categories table
    op.create_table(
        "telegram_shop_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_ts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.UniqueConstraint("tenant_id", "name", name="uq_tg_shop_categories_tenant_name"),
    )
    op.create_index(
        "idx_tg_shop_categories_tenant",
        "telegram_shop_categories",
        ["tenant_id"],
    )
    op.create_index(
        "idx_tg_shop_categories_tenant_sort",
        "telegram_shop_categories",
        ["tenant_id", "sort", "id"],
    )

    # 2) add category_id to products
    op.add_column(
        "telegram_shop_products",
        sa.Column("category_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "idx_tg_shop_products_tenant_category",
        "telegram_shop_products",
        ["tenant_id", "category_id"],
    )

    # 3) backfill: create default category "Без категорії" for each tenant that has products
    # and attach all existing products without category to it.
    # Postgres-safe SQL.
    op.execute(
        """
        WITH tenants AS (
            SELECT DISTINCT tenant_id
            FROM telegram_shop_products
        ),
        ins AS (
            INSERT INTO telegram_shop_categories (tenant_id, name, sort, created_ts)
            SELECT t.tenant_id, 'Без категорії', 0, EXTRACT(EPOCH FROM NOW())::int
            FROM tenants t
            ON CONFLICT (tenant_id, name) DO NOTHING
            RETURNING tenant_id, id
        )
        UPDATE telegram_shop_products p
        SET category_id = c.id
        FROM telegram_shop_categories c
        WHERE p.tenant_id = c.tenant_id
          AND c.name = 'Без категорії'
          AND p.category_id IS NULL;
        """
    )


def downgrade() -> None:
    op.drop_index("idx_tg_shop_products_tenant_category", table_name="telegram_shop_products")
    op.drop_column("telegram_shop_products", "category_id")

    op.drop_index("idx_tg_shop_categories_tenant_sort", table_name="telegram_shop_categories")
    op.drop_index("idx_tg_shop_categories_tenant", table_name="telegram_shop_categories")
    op.drop_table("telegram_shop_categories")