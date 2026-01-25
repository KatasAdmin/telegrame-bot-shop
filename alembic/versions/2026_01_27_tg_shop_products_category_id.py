"""telegram_shop: add category_id to products

Revision ID: tg_shop_products_catid_0127
Revises: tg_shop_hits_promos_0126a
Create Date: 2026-01-27
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "tg_shop_products_catid_0127"
down_revision = "tg_shop_hits_promos_0126a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "telegram_shop_products",
        sa.Column("category_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "idx_tg_shop_products_tenant_category",
        "telegram_shop_products",
        ["tenant_id", "category_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_tg_shop_products_tenant_category", table_name="telegram_shop_products")
    op.drop_column("telegram_shop_products", "category_id")