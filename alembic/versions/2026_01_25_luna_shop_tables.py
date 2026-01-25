"""luna_shop tables (stub)

Revision ID: luna_shop_tables
Revises: add_withdraw_balance_kop
Create Date: 2026-01-25

Заглушка для видаленого модуля luna_shop.
Потрібна, бо ревізія вже є в історії Alembic (alembic_version).
"""
from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "luna_shop_tables"
down_revision = "add_withdraw_balance_kop"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # no-op (stub)
    pass


def downgrade() -> None:
    # no-op (stub)
    pass