# rent_platform/core/tenant_ctx.py
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional


@dataclass
class Tenant:
    id: str
    bot_token: str


# активний tenant у контексті запиту
_current_tenant: ContextVar[Optional[Tenant]] = ContextVar("current_tenant", default=None)


def set_current_tenant(t: Optional[Tenant]) -> None:
    _current_tenant.set(t)


def get_current_tenant() -> Optional[Tenant]:
    return _current_tenant.get()


def init_tenants() -> None:
    """
    Заглушка на старт.
    Пізніше тут підключимо БД і підвантаження tenant'ів/конфігів.
    """
    return