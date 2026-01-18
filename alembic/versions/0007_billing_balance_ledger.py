"""billing: user balance + ledger + tenant billing fields

Revision ID: 0007_billing_balance_ledger
Revises: 0006_product_key_warnings_trial
Create Date: 2026-01-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_billing_balance_ledger"
down_revision = "0006_trial_warnings_product_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # user balances
    op.create_table(
        "owner_accounts",
        sa.Column("owner_user_id", sa.BigInteger(), primary_key=True),
        sa.Column("balance_kop", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("updated_ts", sa.BigInteger(), nullable=False, server_default="0"),
    )

    # ledger
    op.create_table(
        "billing_ledger",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("owner_user_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.String(length=32), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),  # topup|charge|adjust
        sa.Column("amount_kop", sa.BigInteger(), nullable=False),  # + / -
        sa.Column("meta", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_ts", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.create_index("ix_ledger_owner", "billing_ledger", ["owner_user_id"])
    op.create_index("ix_ledger_tenant", "billing_ledger", ["tenant_id"])

    # tenants billing fields
    op.add_column(
        "tenants",
        sa.Column("rate_per_min_kop", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "tenants",
        sa.Column("last_billed_ts", sa.BigInteger(), nullable=False, server_default="0"),
    )

    op.create_index("ix_tenants_last_billed_ts", "tenants", ["last_billed_ts"])


def downgrade() -> None:
    op.drop_index("ix_tenants_last_billed_ts", table_name="tenants")
    op.drop_column("tenants", "last_billed_ts")
    op.drop_column("tenants", "rate_per_min_kop")

    op.drop_index("ix_ledger_tenant", table_name="billing_ledger")
    op.drop_index("ix_ledger_owner", table_name="billing_ledger")
    op.drop_table("billing_ledger")

    op.drop_table("owner_accounts")