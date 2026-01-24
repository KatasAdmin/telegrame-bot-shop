from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from rent_platform.modules.shop.storage import ShopDB, cart_total_uah


def kb_home() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Каталог", callback_data="shop:catalog")],
        [InlineKeyboardButton(text="🧺 Кошик", callback_data="shop:cart")],
        [InlineKeyboardButton(text="🔥 Хіти / Акції", callback_data="shop:hot")],
        [InlineKeyboardButton(text="⭐ Обране", callback_data="shop:fav")],
        [InlineKeyboardButton(text="📞 Підтримка", callback_data="shop:support")],
        [InlineKeyboardButton(text="🧾 Історія", callback_data="shop:orders")],
    ])


def kb_back_home() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="shop:home")],
    ])


def kb_categories(db: ShopDB) -> InlineKeyboardMarkup:
    rows = []
    for c in db.categories.values():
        if not c.enabled:
            continue
        rows.append([InlineKeyboardButton(text=c.title, callback_data=f"shop:cat:{c.id}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="shop:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_product(product_id: str, in_fav: bool) -> InlineKeyboardMarkup:
    fav_text = "⭐ В обраному" if in_fav else "☆ В обране"
    fav_cb = "shop:fav:del:" + product_id if in_fav else "shop:fav:add:" + product_id

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧺 Додати в кошик", callback_data=f"shop:cart:add:{product_id}")],
        [InlineKeyboardButton(text=fav_text, callback_data=fav_cb)],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="shop:catalog")],
    ])


def kb_cart(db: ShopDB, user_id: int) -> InlineKeyboardMarkup:
    """
    Кнопки по товарах + checkout.
    """
    cart = db.carts.get(int(user_id), {})
    rows = []

    # кнопка на кожен товар
    for it in cart.values():
        p = db.products.get(it.product_id)
        if not p:
            continue
        rows.append([InlineKeyboardButton(
            text=f"{p.title} • {it.qty} шт",
            callback_data=f"shop:cart:item:{p.id}"
        )])

    total = cart_total_uah(db, user_id)
    if total > 0:
        rows.append([InlineKeyboardButton(text=f"✅ Оформити • {total} грн", callback_data="shop:checkout")])

    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="shop:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_cart_item(product_id: str, qty: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➖", callback_data=f"shop:cart:dec:{product_id}"),
            InlineKeyboardButton(text=f"{qty}", callback_data="noop"),
            InlineKeyboardButton(text="➕", callback_data=f"shop:cart:inc:{product_id}"),
            InlineKeyboardButton(text="🗑", callback_data=f"shop:cart:rm:{product_id}"),
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="shop:cart")],
    ])


def kb_favorites(db: ShopDB, user_id: int) -> InlineKeyboardMarkup:
    fav = db.favorites.get(int(user_id), {})
    rows = []
    for pid in fav.keys():
        p = db.products.get(pid)
        if not p:
            continue
        rows.append([InlineKeyboardButton(text=p.title, callback_data=f"shop:prod:{p.id}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="shop:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_hot() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 Хіти", callback_data="shop:hot:hits")],
        [InlineKeyboardButton(text="🏷 Акції", callback_data="shop:hot:sales")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="shop:home")],
    ])