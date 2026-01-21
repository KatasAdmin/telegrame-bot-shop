from __future__ import annotations

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column

from rent_platform.db.base import Base


# =========================================================
# Tenants
# =========================================================
class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    bot_token: Mapped[str] = mapped_column(String(256), nullable=False)
    secret: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_ts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class TenantModule(Base):
    __tablename__ = "tenant_modules"
    __table_args__ = (
        UniqueConstraint("tenant_id", "module_key", name="uq_tenant_module"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    module_key: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


# =========================================================
# Referral system (Platform)
# =========================================================

class RefUser(Base):
    """
    Хто кого запросив.
    Один user_id може мати тільки одного referrer_id (назавжди).
    """
    __tablename__ = "ref_users"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_ref_user_user_id"),
        Index("ix_ref_users_referrer_id", "referrer_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(Integer, nullable=False)          # реферал (кого привели)
    referrer_id: Mapped[int] = mapped_column(Integer, nullable=False)      # партнер (хто привів)

    created_ts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class RefBalance(Base):
    """
    Баланс партнера.
    available_kop — можна виводити
    total_earned_kop — зароблено всього
    total_paid_kop — вже виплачено
    """
    __tablename__ = "ref_balances"
    __table_args__ = (
        UniqueConstraint("referrer_id", name="uq_ref_balance_referrer_id"),
    )

    referrer_id: Mapped[int] = mapped_column(Integer, primary_key=True)  # 1 рядок на партнера

    available_kop: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_earned_kop: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_paid_kop: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    updated_ts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class RefLedger(Base):
    """
    Прозорий журнал нарахувань/списань (як ledger).
    kind:
      - topup   (від поповнення)
      - billing (від списань білінгу)
      - bonus   (разовий бонус)
      - payout  (виплата)
      - adjust  (ручна корекція адміном)
    amount_kop:
      + нарахування, - списання
    """
    __tablename__ = "ref_ledger"
    __table_args__ = (
        Index("ix_ref_ledger_referrer_id", "referrer_id"),
        Index("ix_ref_ledger_user_id", "user_id"),
        Index("ix_ref_ledger_kind_ts", "kind", "created_ts"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    referrer_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=True)  # хто приніс дохід (може бути None)

    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    amount_kop: Mapped[int] = mapped_column(Integer, nullable=False)

    title: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    details: Mapped[str] = mapped_column(String(512), nullable=False, default="")

    created_ts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class RefPayoutRequest(Base):
    """
    Заявка на виплату партнерки.
    status: pending|approved|paid|rejected
    """
    __tablename__ = "ref_payout_requests"
    __table_args__ = (
        Index("ix_ref_payout_referrer_status", "referrer_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    referrer_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    amount_kop: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_ts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # опційно: реквізити/метод, але краще зберігати в окремій таблиці або json у майбутньому
    note: Mapped[str] = mapped_column(String(256), nullable=False, default="")


class PlatformSetting(Base):
    """
    Універсальні налаштування платформи (під адмінку).
    key -> value_str
    """
    __tablename__ = "platform_settings"
    __table_args__ = (UniqueConstraint("key", name="uq_platform_settings_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    key: Mapped[str] = mapped_column(String(64), nullable=False)
    value_str: Mapped[str] = mapped_column(String(2048), nullable=False, default="")

    updated_ts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)