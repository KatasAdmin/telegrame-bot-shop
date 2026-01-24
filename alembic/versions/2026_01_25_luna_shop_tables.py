"""luna_shop promos & hits

Revision ID: luna_shop_promos_hits
Revises: luna_shop_tables
Create Date: 2026-01-25
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "luna_shop_promos_hits"
down_revision = "luna_shop_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 🔥 Хіти
    op.add_column(
        "luna_shop_products",
        sa.Column(
            "is_hit",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # 🏷 Акції
    # promo_price_kop: якщо NULL -> акції нема
    op.add_column(
        "luna_shop_products",
        sa.Column(
            "promo_price_kop",
            sa.Integer(),
            nullable=True,
        ),
    )

    # promo_until_ts: 0 -> без обмеження по часу (або не використовується)
    op.add_column(
        "luna_shop_products",
        sa.Column(
            "promo_until_ts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    # індекси (щоб швидко діставати хіти/акції по tenant)
    op.create_index(
        "idx_luna_shop_products_tenant_hit",
        "luna_shop_products",
        ["tenant_id", "is_hit"],
    )
    op.create_index(
        "idx_luna_shop_products_tenant_promo",
        "luna_shop_products",
        ["tenant_id", "promo_until_ts"],
    )

    # прибираємо дефолти там, де не потрібні після створення
    op.alter_column("luna_shop_products", "is_hit", server_default=None)
    op.alter_column("luna_shop_products", "promo_until_ts", server_default=None)


def downgrade() -> None:
    op.drop_index("idx_luna_shop_products_tenant_promo", table_name="luna_shop_products")
    op.drop_index("idx_luna_shop_products_tenant_hit", table_name="luna_shop_products")

    op.drop_column("luna_shop_products", "promo_until_ts")
    op.drop_column("luna_shop_products", "promo_price_kop")
    op.drop_column("luna_shop_products", "is_hit")