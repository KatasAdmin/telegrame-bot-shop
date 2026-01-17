# rent_platform/core/tenant_ctx.py
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional, Iterable

from aiogram import Bot

from rent_platform.config import settings


@dataclass(frozen=True)
class Tenant:
    id: str              # bot_id у твоєму RAM storage
    bot_token: str       # токен tenant-бота
    secret: str          # секрет у webhook URL
    active_modules: tuple[str, ...] = ("shop",)


# активний tenant у контексті запиту
_current_tenant: ContextVar[Optional[Tenant]] = ContextVar("current_tenant", default=None)

# registry (поки RAM)
_TENANTS: dict[str, Tenant] = {}  # tenant_id(bot_id) -> Tenant


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


def upsert_tenant(
    *,
    tenant_id: str,
    bot_token: str,
    secret: str,
    active_modules: Iterable[str] = ("shop",),
) -> Tenant:
    t = Tenant(
        id=tenant_id,
        bot_token=bot_token,
        secret=secret,
        active_modules=tuple(active_modules),
    )
    _TENANTS[tenant_id] = t
    return t


def get_tenant(tenant_id: str) -> Optional[Tenant]:
    return _TENANTS.get(tenant_id)


def tenant_webhook_url(tenant_id: str, secret: str) -> str:
    base = settings.WEBHOOK_URL.rstrip("/")
    prefix = settings.TENANT_WEBHOOK_PREFIX.rstrip("/")
    return f"{base}{prefix}/{tenant_id}/{secret}"


async def ensure_tenant_webhook(tenant: Tenant) -> None:
    """
    Ставить webhook tenant-боту на /tg/t/{bot_id}/{secret}.
    """
    url = tenant_webhook_url(tenant.id, tenant.secret)
    bot = Bot(token=tenant.bot_token)
    try:
        info = await bot.get_webhook_info()
        if (info.url or "").strip() == url:
            return

        await bot.set_webhook(
            url,
            drop_pending_updates=False,
            allowed_updates=["message", "callback_query"],
        )
    finally:
        await bot.session.close()