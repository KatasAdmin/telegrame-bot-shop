from __future__ import annotations

from typing import Any

PRODUCT_CATALOG: dict[str, dict[str, Any]] = {
    "shop_bot": {
        "title": "🛒 Luna Shop Bot",
        "short": "Магазин-бот (скелет + UI + адмін-додавання товарів)",
        "desc": (
            "🛒 <b>Luna Shop Bot</b>\n\n"
            "Скелет магазину з 6 кнопками, кошиком, обраним та замовленнями.\n"
            "Адмін може додавати категорії/товари командами прямо в боті.\n"
        ),
        "rate_per_min_uah": 0.02,
        "module_key": "shop_bot",
        "handler": "rent_platform.modules.shop.router:handle_update",
    }
}