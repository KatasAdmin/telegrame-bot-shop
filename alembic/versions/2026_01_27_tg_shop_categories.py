"""telegram_shop: categories + product.category_id

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
    )

    op.create_index(
        "idx_tg_shop_categories_tenant",
        "telegram_shop_categories",
        ["tenant_id"],
    )

    op.create_index(
        "uq_tg_shop_categories_tenant_name",
        "telegram_shop_categories",
        ["tenant_id", "name"],
        unique=True,
    )

    # 2) add category_id to products (nullable)
    op.add_column(
        "telegram_shop_products",
        sa.Column("category_id", sa.Integer(), nullable=True),
    )

    # optional FK (можна прибрати якщо не хочеш)
    op.create_foreign_key(
        "fk_tg_shop_products_category_id",
        "telegram_shop_products",
        "telegram_shop_categories",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index(
        "idx_tg_shop_products_tenant_category_active",
        "telegram_shop_products",
        ["tenant_id", "category_id", "is_active", "id"],
    )


def downgrade() -> None:
    op.drop_index("idx_tg_shop_products_tenant_category_active", table_name="telegram_shop_products")
    op.drop_constraint("fk_tg_shop_products_category_id", "telegram_shop_products", type_="foreignkey")
    op.drop_column("telegram_shop_products", "category_id")

    op.drop_index("uq_tg_shop_categories_tenant_name", table_name="telegram_shop_categories")
    op.drop_index("idx_tg_shop_categories_tenant", table_name="telegram_shop_categories")
    op.drop_table("telegram_shop_categories")