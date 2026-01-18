# rent_platform/core/modules.py
from __future__ import annotations

import logging

from rent_platform.core.registry import register_module

log = logging.getLogger(__name__)


def init_modules() -> None:
    # core
    try:
        from rent_platform.modules.core.router import handle_update as core_handler
        register_module("core", core_handler)
    except Exception as e:
        log.exception("Failed to init module 'core': %s", e)
        raise

    # shop (старий модуль, поки лишаємо як є)
    try:
        from rent_platform.modules.shop.router import handle_update as shop_handler
        register_module("shop", shop_handler)
    except Exception as e:
        log.exception("Failed to init module 'shop': %s", e)
        raise

    # shop_bot (маркетплейс продукт Luna Shop Bot)
    try:
        from rent_platform.modules.shop_bot import shop_bot_module
        register_module("shop_bot", shop_bot_module)
    except Exception as e:
        log.exception("Failed to init module 'shop_bot': %s", e)
        raise