# rent_platform/core/modules.py
from __future__ import annotations

import logging

from rent_platform.core.registry import register_module

log = logging.getLogger(__name__)


def init_modules() -> None:
    # ✅ імпортуємо модулі ЛИШЕ коли стартуємо сервіс
    # так легше дебажити і не вбиває імпорт дерева одразу
    try:
        from rent_platform.modules.shop.router import handle_update as shop_handler
        register_module("shop", shop_handler)
    except Exception as e:
        log.exception("Failed to init module 'shop': %s", e)
        # якщо хочеш щоб сервіс падав при проблемі модуля — re-raise
        raise