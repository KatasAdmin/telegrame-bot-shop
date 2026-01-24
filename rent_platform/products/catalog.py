# rent_platform/products/catalog.py
from __future__ import annotations

from typing import Any

PRODUCT_CATALOG: dict[str, dict[str, Any]] = {
    "telegram_shop": {
        "title": "🛒 Телеграм магазин",
        "short": "Магазин-бот (скелет + UI + адмін-додавання товарів)",
        "desc": (
            "🛒 <b>Телеграм магазин</b>\n\n"
            "Готовий каркас магазину:\n"
            "• Каталог / категорії / товари\n"
            "• Кошик (пізніше)\n"
            "• Замовлення (пізніше)\n"
            "• Адмін-команди для додавання товарів\n"
        ),
        "rate_per_min_uah": 0.02,

        # ВАЖЛИВО: module_key — це те, що буде в tenant_modules і в tenants.product_key
        "module_key": "luna_shop",
        "handler": "rent_platform.modules.luna_shop.router:handle_update",
    },
}