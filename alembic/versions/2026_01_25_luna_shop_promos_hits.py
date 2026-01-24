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
    # --- PROMOS (акції) ---
    op.create_table(
        "luna_shop_promos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("desc", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_ts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("promo_until_ts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "idx_luna_shop_promos_tenant",
        "luna_shop_promos",
        ["tenant_id"],
    )
    op.create_index(
        "idx_luna_shop_promos_tenant_active",
        "luna_shop_promos",
        ["tenant_id", "is_active"],
    )

    # --- HITS (хіти) ---
    op.create_table(
        "luna_shop_hits",
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("tenant_id", "product_id"),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["luna_shop_products.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "idx_luna_shop_hits_tenant_active",
        "luna_shop_hits",
        ["tenant_id", "is_active"],
    )


def downgrade() -> None:
    op.drop_index("idx_luna_shop_hits_tenant_active", table_name="luna_shop_hits")
    op.drop_table("luna_shop_hits")

    op.drop_index("idx_luna_shop_promos_tenant_active", table_name="luna_shop_promos")
    op.drop_index("idx_luna_shop_promos_tenant", table_name="luna_shop_promos")
    op.drop_table("luna_shop_promos")