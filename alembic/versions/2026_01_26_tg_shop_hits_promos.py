"""telegram_shop: hits + promos columns

Revision ID: tg_shop_hits_promos_0126a
Revises: tg_shop_desc_photos_0126
Create Date: 2026-01-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "tg_shop_hits_promos_0126a"
down_revision = "tg_shop_desc_photos_0126"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "telegram_shop_products",
        sa.Column("is_hit", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "telegram_shop_products",
        sa.Column("promo_price_kop", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "telegram_shop_products",
        sa.Column("promo_until_ts", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_column("telegram_shop_products", "promo_until_ts")
    op.drop_column("telegram_shop_products", "promo_price_kop")
    op.drop_column("telegram_shop_products", "is_hit")