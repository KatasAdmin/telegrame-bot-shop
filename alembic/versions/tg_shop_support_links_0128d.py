# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "tg_shop_support_links_0128d"
down_revision = "tg_shop_order_items_sku_0128c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_shop_support_links",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column("url", sa.Text(), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sort", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("created_ts", sa.Integer(), nullable=False),
        sa.Column("updated_ts", sa.Integer(), nullable=False),
    )
    op.create_index("ix_tgshop_support_tenant", "telegram_shop_support_links", ["tenant_id"])
    op.create_index("ix_tgshop_support_tenant_enabled_sort", "telegram_shop_support_links", ["tenant_id", "enabled", "sort", "id"])
    op.create_unique_constraint("uq_tgshop_support_tenant_key", "telegram_shop_support_links", ["tenant_id", "key"])


def downgrade() -> None:
    op.drop_constraint("uq_tgshop_support_tenant_key", "telegram_shop_support_links", type_="unique")
    op.drop_index("ix_tgshop_support_tenant_enabled_sort", table_name="telegram_shop_support_links")
    op.drop_index("ix_tgshop_support_tenant", table_name="telegram_shop_support_links")
    op.drop_table("telegram_shop_support_links")