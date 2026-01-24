from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import time
import uuid


@dataclass
class Category:
    id: str
    title: str
    enabled: bool = True


@dataclass
class Product:
    id: str
    category_id: str
    title: str
    desc: str
    price_uah: int
    photos: List[str] = field(default_factory=list)  # file_id або URL
    enabled: bool = True
    is_hit: bool = False
    old_price_uah: int = 0  # якщо >0 і > price -> акція
    created_ts: int = field(default_factory=lambda: int(time.time()))


@dataclass
class CartItem:
    product_id: str
    qty: int = 1


@dataclass
class Order:
    id: str
    user_id: int
    items: List[CartItem]
    total_uah: int
    created_ts: int
    status: str = "new"  # new/confirmed/done/canceled
    contact: str = ""    # потім: телефон/нік/коментар


@dataclass
class ShopDB:
    categories: Dict[str, Category] = field(default_factory=dict)
    products: Dict[str, Product] = field(default_factory=dict)

    carts: Dict[int, Dict[str, CartItem]] = field(default_factory=dict)     # user_id -> product_id -> CartItem
    favorites: Dict[int, Dict[str, int]] = field(default_factory=dict)      # user_id -> product_id -> 1
    orders: Dict[int, List[Order]] = field(default_factory=dict)            # user_id -> list[Order]

    # UI state: одне “живе” повідомлення на юзера (щоб переливалось)
    ui_message_id: Dict[int, int] = field(default_factory=dict)             # user_id -> message_id


SHOP_DB: dict[str, ShopDB] = {}  # tenant_id -> ShopDB


def get_shop_db(tenant_id: str) -> ShopDB:
    if tenant_id not in SHOP_DB:
        SHOP_DB[tenant_id] = ShopDB()
        seed_demo(SHOP_DB[tenant_id])
    return SHOP_DB[tenant_id]


def seed_demo(db: ShopDB) -> None:
    """
    Демо-дані, щоб ти міг тестити з другого акаунту одразу.
    Потім адмінкою будемо це редагувати/створювати.
    """
    if db.categories:
        return

    c1 = Category(id="c_shoes", title="Взуття")
    c2 = Category(id="c_access", title="Аксесуари")
    db.categories[c1.id] = c1
    db.categories[c2.id] = c2

    p1 = Product(
        id="p_sneakers",
        category_id=c1.id,
        title="Кросівки Luna Street",
        desc="Зручні, легкі, на кожен день.",
        price_uah=1899,
        photos=[],  # потім додаси file_id в адмінці
        is_hit=True,
    )
    p2 = Product(
        id="p_boots",
        category_id=c1.id,
        title="Черевики Luna Winter",
        desc="Теплі, міцні, для зими.",
        price_uah=2499,
        old_price_uah=2999,  # акція
        photos=[],
        is_hit=False,
    )
    p3 = Product(
        id="p_bag",
        category_id=c2.id,
        title="Сумка Luna Mini",
        desc="Мінімалістична сумка через плече.",
        price_uah=999,
        photos=[],
    )

    for p in (p1, p2, p3):
        db.products[p.id] = p


def cart_get(db: ShopDB, user_id: int) -> Dict[str, CartItem]:
    return db.carts.setdefault(int(user_id), {})


def fav_get(db: ShopDB, user_id: int) -> Dict[str, int]:
    return db.favorites.setdefault(int(user_id), {})


def orders_get(db: ShopDB, user_id: int) -> List[Order]:
    return db.orders.setdefault(int(user_id), [])


def cart_total_uah(db: ShopDB, user_id: int) -> int:
    cart = cart_get(db, user_id)
    total = 0
    for it in cart.values():
        p = db.products.get(it.product_id)
        if not p or not p.enabled:
            continue
        total += int(p.price_uah) * int(it.qty)
    return int(total)


def make_order_from_cart(db: ShopDB, user_id: int) -> Optional[Order]:
    cart = cart_get(db, user_id)
    if not cart:
        return None

    items = [CartItem(product_id=x.product_id, qty=int(x.qty)) for x in cart.values() if x.qty > 0]
    if not items:
        return None

    total = cart_total_uah(db, user_id)
    oid = f"o_{uuid.uuid4().hex[:8]}"
    o = Order(
        id=oid,
        user_id=int(user_id),
        items=items,
        total_uah=int(total),
        created_ts=int(time.time()),
        status="new",
    )
    orders_get(db, user_id).insert(0, o)
    cart.clear()
    return o