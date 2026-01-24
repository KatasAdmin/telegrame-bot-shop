# rent_platform/modules/telegram_shop/storage.py
from __future__ import annotations

SHOP_DB: dict[str, dict] = {}


def get_shop_db(tenant_id: str) -> dict:
    if tenant_id not in SHOP_DB:
        SHOP_DB[tenant_id] = {
            "products": [],  # list[dict]
            "orders": [],    # list[dict]
        }
    return SHOP_DB[tenant_id]