# rent_platform/products/catalog.py
from __future__ import annotations
from typing import Any, Dict

PRODUCT_CATALOG: Dict[str, Dict[str, Any]] = {
    "shop_bot": {
        "title": "🛒 Luna Shop Bot",
        "short": "Магазин-бот: каталог, кошик, замовлення",
        "desc": (
            "🛒 <b>Luna Shop Bot</b>\n\n"
            "Готовий Telegram-магазин, який ти береш в оренду.\n\n"
            "<b>MVP:</b>\n"
            "• Каталог і категорії\n"
            "• Кошик\n"
            "• Замовлення і історія\n\n"
            "Оплати напряму на твої ключі."
        ),

        # 💰 ТУТ тариф
        "rate_per_min_uah": 0.02,

        # 🔌 модуль
        "module_key": "shop",
        "handler": "rent_platform.modules.shop.router:handle_update",
    },
}