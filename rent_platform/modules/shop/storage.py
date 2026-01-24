from __future__ import annotations

from typing import Any

SHOP_DB: dict[str, dict[str, Any]] = {}


def get_shop_db(tenant_id: str) -> dict[str, Any]:
    """
    In-memory storage per tenant.
    Далі замінимо на БД, але інтерфейс лишимо такий самий.
    """
    if tenant_id not in SHOP_DB:
        SHOP_DB[tenant_id] = {
            "settings": {
                "support_text": "📞 Підтримка: +380…\n🕘 10:00–19:00",
                "btn_catalog": "🛍 Каталог",
                "btn_cart": "🛒 Кошик",
                "btn_fav": "⭐️ Обране",
                "btn_hits": "🔥 Хіти/Акції",
                "btn_support": "🆘 Підтримка",
                "btn_orders": "📜 Історія",
            },
            "categories": [],   # {id, title}
            "products": [],     # {id, category_id, title, price_uah, desc, images[], is_hit, is_sale}
            "favorites": {},    # user_id -> set(product_id)
            "carts": {},        # user_id -> {product_id: qty}
            "orders": [],       # {id, user_id, items, total_uah, created_ts, status}
        }
    return SHOP_DB[tenant_id]