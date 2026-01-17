# rent_platform/modules/shop/storage.py

# ⚠️ ПОКИ in-memory
SHOP_DB: dict[str, dict] = {}


def get_shop_db(tenant_id: str) -> dict:
    if tenant_id not in SHOP_DB:
        SHOP_DB[tenant_id] = {
            "products": [],
            "orders": []
        }
    return SHOP_DB[tenant_id]