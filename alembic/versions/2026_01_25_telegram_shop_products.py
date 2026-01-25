"""telegram_shop products

Revision ID: tg_shop_products_0125
Revises: add_withdraw_balance_kop
Create Date: 2026-01-25
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "tg_shop_products_0125"
down_revision = "add_withdraw_balance_kop"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # products
    op.create_table(
        "telegram_shop_products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("price_kop", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_ts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "idx_tg_shop_products_tenant",
        "telegram_shop_products",
        ["tenant_id"],
    )

    # cart
    op.create_table(
        "telegram_shop_cart_items",
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_ts", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("tenant_id", "user_id", "product_id"),
    )
    op.create_index(
        "idx_tg_shop_cart_tenant_user",
        "telegram_shop_cart_items",
        ["tenant_id", "user_id"],
    )

    # orders
    op.create_table(
        "telegram_shop_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'new'")),
        sa.Column("total_kop", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_ts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "idx_tg_shop_orders_tenant_user",
        "telegram_shop_orders",
        ["tenant_id", "user_id"],
    )

    op.create_table(
        "telegram_shop_order_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("price_kop", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("qty", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["telegram_shop_orders.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "idx_tg_shop_order_items_order",
        "telegram_shop_order_items",
        ["order_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_tg_shop_order_items_order", table_name="telegram_shop_order_items")
    op.drop_table("telegram_shop_order_items")

    op.drop_index("idx_tg_shop_orders_tenant_user", table_name="telegram_shop_orders")
    op.drop_table("telegram_shop_orders")

    op.drop_index("idx_tg_shop_cart_tenant_user", table_name="telegram_shop_cart_items")
    op.drop_table("telegram_shop_cart_items")

    op.drop_index("idx_tg_shop_products_tenant", table_name="telegram_shop_products")
    op.drop_table("telegram_shop_products")