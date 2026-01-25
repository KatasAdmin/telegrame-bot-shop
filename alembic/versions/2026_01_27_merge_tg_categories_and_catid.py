"""merge heads: tg_shop categories + products category_id

Revision ID: merge_tg_cats_catid_0127m
Revises: tg_shop_categories_0127, tg_shop_products_catid_0127
Create Date: 2026-01-27

Це merge-міграція: зливає 2 head-и в один.
Нічого в БД не робить.
"""
from __future__ import annotations

from alembic import op

revision = "merge_tg_cats_catid_0127m"
down_revision = ("tg_shop_categories_0127", "tg_shop_products_catid_0127")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # no-op (merge point)
    pass


def downgrade() -> None:
    # no-op (merge point)
    pass