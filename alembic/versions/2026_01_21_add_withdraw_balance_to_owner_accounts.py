from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "add_withdraw_balance_kop"
down_revision = "0008_invoices_topup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "owner_accounts",
        sa.Column(
            "withdraw_balance_kop",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
    )

    # прибираємо default після створення
    op.alter_column(
        "owner_accounts",
        "withdraw_balance_kop",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("owner_accounts", "withdraw_balance_kop")