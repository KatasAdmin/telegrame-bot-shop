from __future__ import annotations

from typing import Awaitable, Callable, Any

from aiogram import Bot
from rent_platform.core.tenant_ctx import Tenant

ModuleHandler = Callable[[Tenant, dict[str, Any], Bot], Awaitable[bool]]

MODULES: dict[str, ModuleHandler] = {}


def register_module(key: str, handler: ModuleHandler) -> None:
    MODULES[key] = handler


def get_module(key: str) -> ModuleHandler | None:
    return MODULES.get(key)


def list_modules() -> list[str]:
    return sorted(MODULES.keys())