# -*- coding: utf-8 -*-
from __future__ import annotations

"""
telegram_shop: integrations/settings (keys for FOP, Nova Poshta, etc)

Revision ID: tg_shop_integrations_0130a
Revises: merge_tg_shop_support_pay_0129m
Create Date: 2026-01-29
"""

import time
from alembic import op
import sqlalchemy as sa

revision = "tg_shop_integrations_0130a"
down_revision = "merge_tg_shop_support_pay_0129m"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_shop_integrations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),

        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),

        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("value", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("hint", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("sort", sa.Integer(), nullable=False, server_default=sa.text("0")),

        sa.Column("created_ts", sa.Integer(), nullable=False, default=lambda: int(time.time())),
        sa.Column("updated_ts", sa.Integer(), nullable=False, default=lambda: int(time.time())),

        sa.UniqueConstraint("tenant_id", "key", name="uq_tgshop_integrations_tenant_key"),
    )

    op.create_index(
        "ix_tgshop_integrations_tenant",
        "telegram_shop_integrations",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_tgshop_integrations_tenant_enabled",
        "telegram_shop_integrations",
        ["tenant_id", "enabled"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tgshop_integrations_tenant_enabled", table_name="telegram_shop_integrations")
    op.drop_index("ix_tgshop_integrations_tenant", table_name="telegram_shop_integrations")
    op.drop_table("telegram_shop_integrations")
