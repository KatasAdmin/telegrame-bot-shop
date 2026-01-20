"""topups: invoices table

Revision ID: 0008_invoices_topup
Revises: 0007_billing_balance_ledger
Create Date: 2026-01-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_invoices_topup"
down_revision = "0007_billing_balance_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing_invoices",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("owner_user_id", sa.BigInteger(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),  # mono|privat|cryptobot|...
        sa.Column("amount_kop", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),  # pending|paid|cancelled
        sa.Column("pay_url", sa.Text(), nullable=True),
        sa.Column("meta", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_ts", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("paid_ts", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.create_index("ix_invoices_owner", "billing_invoices", ["owner_user_id"])
    op.create_index("ix_invoices_status", "billing_invoices", ["status"])


def downgrade() -> None:
    op.drop_index("ix_invoices_status", table_name="billing_invoices")
    op.drop_index("ix_invoices_owner", table_name="billing_invoices")
    op.drop_table("billing_invoices")