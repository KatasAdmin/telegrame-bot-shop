# rent_platform/core/registry.py
from __future__ import annotations

from typing import Awaitable, Callable, Any

# Один модуль = одна async-функція/хендлер (може бути router factory пізніше)
ModuleHandler = Callable[..., Awaitable[Any]]

MODULES: dict[str, ModuleHandler] = {}


def register_module(key: str, handler: ModuleHandler) -> None:
    MODULES[key] = handler


def get_module(key: str) -> ModuleHandler | None:
    return MODULES.get(key)


def list_modules() -> list[str]:
    return sorted(MODULES.keys())