"""owner_user_id bigint

Revision ID: 0002_owner_user_id_bigint
Revises: 0001_init
Create Date: 2026-01-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_owner_user_id_bigint"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "tenants",
        "owner_user_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "tenants",
        "owner_user_id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        nullable=False,
    )