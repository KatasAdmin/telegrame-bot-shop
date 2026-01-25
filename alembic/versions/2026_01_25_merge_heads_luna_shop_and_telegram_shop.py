"""merge heads: luna_shop + telegram_shop

Revision ID: merge_luna_tg_0125
Revises: luna_shop_promos_hits, tg_shop_products_0125
Create Date: 2026-01-25

Це merge-міграція, яка зливає дві гілки в один head.
Нічого в БД не робить.
"""
from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "merge_luna_tg_0125"
down_revision = ("luna_shop_promos_hits", "tg_shop_products_0125")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # no-op (merge point)
    pass


def downgrade() -> None:
    # no-op (merge point)
    pass