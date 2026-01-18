# rent_platform/products/catalog.py
from __future__ import annotations

from typing import Any, Dict

PRODUCT_CATALOG: Dict[str, Dict[str, Any]] = {
    "shop_bot": {
        "title": "🛒 Luna Shop Bot",
        "short": "Магазин-бот: товари, кошик, замовлення (MVP)",
        "desc": (
            "🛒 *Luna Shop Bot*\n\n"
            "Це готовий бот-магазин, який ти береш в оренду і налаштовуєш під себе.\n\n"
            "*Що вміє (MVP):*\n"
            "• Каталог / категорії / товари\n"
            "• Кошик + оформлення\n"
            "• Замовлення + статуси\n\n"
            "*Оплати (режим 2):*\n"
            "Ти додаєш свої ключі Mono/Privat/CryptoBot — гроші йдуть тобі.\n\n"
            "_Критичні ключі платформи сховані._"
        ),
        "rate_per_min_uah": 0.02,

        # 👇 ГОЛОВНЕ: який модуль в tenant увімкнути + де handler
        "module_key": "shop_bot",
        "handler": "rent_platform.modules.shop_bot:handle_update",
    },

    # Далі додаєш інші продукти так само:
    # "crm_bot": {..., "module_key": "crm_bot", "handler": "rent_platform.modules.crm_bot:handle_update"},
}