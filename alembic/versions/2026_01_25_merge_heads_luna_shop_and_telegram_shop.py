"""merge heads: luna_shop_promos_hits + telegram_shop_products

Revision ID: 2026_01_25_merge_heads_luna_telegram
Revises: luna_shop_promos_hits, 2026_01_25_telegram_shop_products
Create Date: 2026-01-25

Це merge-ревізія (no-op). Потрібна, бо в репозиторії зʼявилось 2 head-и.
"""
from __future__ import annotations


# revision identifiers, used by Alembic.
revision = "2026_01_25_merge_heads_luna_telegram"
down_revision = ("luna_shop_promos_hits", "2026_01_25_telegram_shop_products")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # no-op merge
    pass


def downgrade() -> None:
    # no-op merge
    pass