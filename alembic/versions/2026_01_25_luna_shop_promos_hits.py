"""luna_shop promos & hits (stub)

Revision ID: luna_shop_promos_hits
Revises: luna_shop_tables
Create Date: 2026-01-25

Це заглушка, щоб Alembic не падав, якщо ревізія вже є в БД (alembic_version),
але сам файл міграції був видалений разом із модулем luna_shop.
"""
from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "luna_shop_promos_hits"
down_revision = "luna_shop_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # no-op (stub)
    pass


def downgrade() -> None:
    # no-op (stub)
    pass