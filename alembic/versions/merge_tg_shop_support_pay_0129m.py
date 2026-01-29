# -*- coding: utf-8 -*-
from __future__ import annotations

"""
telegram_shop: merge heads (support_links + payment_providers)

Revision ID: merge_tg_shop_support_pay_0129m
Revises: tg_shop_support_links_0128d, tg_shop_payment_providers_0129p
Create Date: 2026-01-29
"""

from alembic import op  # noqa: F401

revision = "merge_tg_shop_support_pay_0129m"
down_revision = ("tg_shop_support_links_0128d", "tg_shop_payment_providers_0129p")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # merge-only ревізія, без змін
    pass


def downgrade() -> None:
    # merge-only ревізія, без змін
    pass
