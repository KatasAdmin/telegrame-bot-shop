from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from rent_platform.db.base import Base


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
    tenant_id: Mapped[str] = mapped_column(String(32), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    module_key: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)