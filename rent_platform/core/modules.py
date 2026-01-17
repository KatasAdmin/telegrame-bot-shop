# rent_platform/core/modules.py
from __future__ import annotations

from rent_platform.core.registry import register_module

# Тут імпорти модулів (реєстрація в одному місці, без дубля в registry.py)
from rent_platform.modules.shop.router import handle_update as shop_handler


def init_modules() -> None:
    register_module("shop", shop_handler)