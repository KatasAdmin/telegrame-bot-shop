# rent_platform/modules/shop_bot/storage.py
from __future__ import annotations

from dataclasses import dataclass, field

# tenant_id -> state
SHOP_DB: dict[str, dict] = {}


@dataclass
class UserState:
    last_msg_id: int = 0
    cart: dict[str, int] = field(default_factory=dict)      # product_id -> qty
    fav: set[str] = field(default_factory=set)              # product_id
    step: str = "menu"                                      # menu/catalog/cart/...
    tmp: dict = field(default_factory=dict)                 # for flows


def get_shop_db(tenant_id: str) -> dict:
    if tenant_id not in SHOP_DB:
        SHOP_DB[tenant_id] = {
            "products": [],   # потім з БД
            "orders": [],     # потім з БД
            "users": {},      # user_id -> UserState
            "categories": [], # потім з БД
            "support": {"text": "📞 Підтримка: @your_support"},  # заглушка
        }
    return SHOP_DB[tenant_id]


def get_user_state(db: dict, user_id: int) -> UserState:
    users = db["users"]
    if user_id not in users:
        users[user_id] = UserState()
    return users[user_id]