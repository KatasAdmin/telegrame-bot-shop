from __future__ import annotations

from typing import Any

PRODUCT_CATALOG: dict[str, dict[str, Any]] = {
    "telegram_shop": {
        "title": "🛒 Телеграм магазин",
        "short": "Каркас магазину + адмін-додавання товарів",
        "desc": (
            "🛒 <b>Телеграм магазин</b>\n\n"
            "Готовий каркас магазину:\n"
            "• Каталог / категорії / товари\n"
            "• Адмін-команди для додавання товарів\n"
            "• Кошик / замовлення — наступним кроком\n"
        ),
        "rate_per_min_uah": 0.02,

        # ВАЖЛИВО: module_key == product_key
        "module_key": "telegram_shop",

        # handler продукту
        "handler": "rent_platform.modules.luna_shop.router:handle_update",

        # welcome для /start (викликає core)
        "welcome": "rent_platform.modules.luna_shop.manifest:get_welcome_text",
    }
}