"""alembic: expand version_num length to 64

Revision ID: tg_alembic_ver_0128
Revises: tg_shop_orders_archive_0128a
Create Date: 2026-01-28
"""
from __future__ import annotations

from alembic import op

revision = "tg_alembic_ver_0128"
down_revision = "tg_shop_orders_archive_0128a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Postgres: standard alembic_version.version_num is VARCHAR(32)
    # We expand it to 64 to allow long revision ids.
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64);")


def downgrade() -> None:
    # rollback to default length
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(32);")