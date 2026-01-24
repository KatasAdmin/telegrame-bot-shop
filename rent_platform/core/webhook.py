from __future__ import annotations

from typing import Any

from aiogram import Bot

from rent_platform.core.tenant_ctx import Tenant
from rent_platform.core.registry import get_module


async def handle_webhook(tenant: Tenant, update: dict[str, Any]) -> None:
    mods = list(tenant.active_modules)

    # core — завжди в кінець
    if "core" in mods:
        mods = [m for m in mods if m != "core"] + ["core"]

    for module_name in mods:
        module = get_module(module_name)
        if not module:
            continue

        handled = await module(tenant, update)
        if handled:
            return