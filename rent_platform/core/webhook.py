from __future__ import annotations

from typing import Any

from aiogram import Bot

from rent_platform.core.tenant_ctx import Tenant
from rent_platform.core.registry import get_module


async def handle_webhook(tenant: Tenant, update: dict[str, Any]) -> None:
    bot = Bot(token=tenant.bot_token)
    try:
        for module_name in tenant.active_modules:
            module = get_module(module_name)
            if not module:
                continue

            handled = await module(tenant, update, bot)
            if handled:
                return
    finally:
        await bot.session.close()