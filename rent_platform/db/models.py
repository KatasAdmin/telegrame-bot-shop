from __future__ import annotations

from sqlalchemy import String, Integer, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rent_platform.db.base import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # bot_id
    owner_user_id: Mapped[int] = mapped_column(Integer, index=True)

    bot_token: Mapped[str] = mapped_column(String(256))  # поки plaintext (далі зашифруємо)
    secret: Mapped[str] = mapped_column(String(128), index=True)

    status: Mapped[str] = mapped_column(String(32), default="active")  # active/paused/expired
    created_ts: Mapped[int] = mapped_column(Integer, default=0)

    modules: Mapped[list["TenantModule"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")


class TenantModule(Base):
    __tablename__ = "tenant_modules"
    __table_args__ = (UniqueConstraint("tenant_id", "module_key", name="uq_tenant_module"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)

    module_key: Mapped[str] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="modules")