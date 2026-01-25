"""telegram_shop: product description + photos

Revision ID: tg_shop_desc_photos_0126
Revises: merge_luna_tg_0125
Create Date: 2026-01-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "tg_shop_desc_photos_0126"
down_revision = "merge_luna_tg_0125"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) product description
    op.add_column(
        "telegram_shop_products",
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
    )

    # 2) product photos (Telegram file_id)
    op.create_table(
        "telegram_shop_product_photos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Text(), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_ts", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["telegram_shop_products.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "idx_tg_shop_photos_tenant_product",
        "telegram_shop_product_photos",
        ["tenant_id", "product_id"],
    )
    op.create_index(
        "idx_tg_shop_photos_tenant_product_sort",
        "telegram_shop_product_photos",
        ["tenant_id", "product_id", "sort"],
    )


def downgrade() -> None:
    op.drop_index("idx_tg_shop_photos_tenant_product_sort", table_name="telegram_shop_product_photos")
    op.drop_index("idx_tg_shop_photos_tenant_product", table_name="telegram_shop_product_photos")
    op.drop_table("telegram_shop_product_photos")

    op.drop_column("telegram_shop_products", "description")