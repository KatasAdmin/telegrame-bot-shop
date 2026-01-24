from __future__ import annotations

from typing import Any

SHOP_DB: dict[str, dict[str, Any]] = {}


def get_shop_db(tenant_id: str) -> dict[str, Any]:
    if tenant_id not in SHOP_DB:
        SHOP_DB[tenant_id] = {
            "settings": {
                "support_text": "📞 Підтримка: +380…\n🕘 10:00–19:00",
                "buttons": {
                    "catalog": "🛍 Каталог",
                    "cart": "🛒 Кошик",
                    "fav": "⭐️ Обране",
                    "hits": "🔥 Хіти/Акції",
                    "support": "🆘 Підтримка",
                    "orders": "📜 Історія",
                },
            },
            "admin": {
                "ids": set(),  # сюди додаси свій user_id командою /shop_admin_add
            },
            "categories": [],  # {id:int, title:str}
            "products": [],    # {id:int, category_id:int, title:str, price_uah:int, desc:str, images:list[str], is_hit:bool, is_sale:bool}
            "favorites": {},   # user_id:int -> set(product_id:int)
            "carts": {},       # user_id:int -> dict[product_id:int, qty:int]
            "orders": [],      # {id:int, user_id:int, items:[{product_id, qty, price_uah}], total_uah:int, created_ts:int, status:str}
            "ui": {},          # user_id:int -> {"last_message_id": int}
            "seq": {"cat": 1, "prod": 1, "order": 1},
        }
    return SHOP_DB[tenant_id]