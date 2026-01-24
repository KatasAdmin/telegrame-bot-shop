from __future__ import annotations

from typing import Any

# ⚠️ MVP: in-memory (потім замінимо на БД)
SHOP_DB: dict[str, dict[str, Any]] = {}


def get_shop_db(tenant_id: str) -> dict[str, Any]:
    """
    Дані магазину окремі для кожного tenant.
    """
    if tenant_id not in SHOP_DB:
        # мінімально: товари + замовлення
        SHOP_DB[tenant_id] = {
            "products": [
                {
                    "id": "p1",
                    "name": "Тестовий товар 1",
                    "price": 100,
                    "desc": "Перший тестовий товар",
                },
                {
                    "id": "p2",
                    "name": "Тестовий товар 2",
                    "price": 250,
                    "desc": "Другий тестовий товар",
                },
            ],
            "orders": [],
        }
    return SHOP_DB[tenant_id]