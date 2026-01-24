from __future__ import annotations

from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


# =========================
# USER REPLY MENUS
# =========================

def main_menu_kb() -> ReplyKeyboardMarkup:
    """
    Головне меню магазину (ЮЗЕР)
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛍 Каталог"), KeyboardButton(text="🔥 Хіти")],
            [KeyboardButton(text="🏷 Акції"), KeyboardButton(text="🛒 Кошик")],
            [KeyboardButton(text="📦 Замовлення"), KeyboardButton(text="ℹ️ Допомога")],
        ],
        resize_keyboard=True,
        selective=True,
    )


def back_to_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🏠 Меню")]],
        resize_keyboard=True,
        selective=True,
    )


# =========================
# INLINE — PRODUCTS LISTS
# =========================

def products_list_kb(products: list[dict]) -> InlineKeyboardMarkup:
    """
    Каталог / Хіти / Акції
    """
    rows: list[list[InlineKeyboardButton]] = []

    for p in products:
        label = p["name"]

        if p.get("has_promo"):
            label = f"🔥 {label}"
        elif p.get("is_hit"):
            label = f"⭐ {label}"

        rows.append(
            [
                InlineKeyboardButton(
                    text=f"➕ {label}",
                    callback_data=f"ls:add:{p['id']}",
                )
            ]
        )

    rows.append([InlineKeyboardButton(text="🛒 Кошик", callback_data="ls:cart")])
    rows.append([InlineKeyboardButton(text="🏠 Меню", callback_data="ls:menu")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


# =========================
# PRODUCT CARD (INLINE)
# =========================

def product_card_kb(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➖", callback_data=f"ls:dec:{product_id}"),
                InlineKeyboardButton(text="➕", callback_data=f"ls:inc:{product_id}"),
                InlineKeyboardButton(text="🗑", callback_data=f"ls:del:{product_id}"),
            ],
            [InlineKeyboardButton(text="🛒 Кошик", callback_data="ls:cart")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="ls:products")],
        ]
    )


# =========================
# CART
# =========================

def cart_kb(has_items: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    rows.append([InlineKeyboardButton(text="🔄 Оновити", callback_data="ls:cart")])

    if has_items:
        rows.append(
            [InlineKeyboardButton(text="✅ Оформити замовлення", callback_data="ls:checkout")]
        )
        rows.append(
            [InlineKeyboardButton(text="🧹 Очистити кошик", callback_data="ls:cart_clear")]
        )

    rows.append([InlineKeyboardButton(text="🛍 Каталог", callback_data="ls:products")])
    rows.append([InlineKeyboardButton(text="🏠 Меню", callback_data="ls:menu")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


# =========================
# ADMIN INLINE (ОКРЕМО)
# =========================

def admin_product_kb(product_id: int) -> InlineKeyboardMarkup:
    """
    ЦЕ БАЧИТЬ ТІЛЬКИ АДМІН
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⭐ Зробити хітом",
                    callback_data=f"ls:a_hit:{product_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏷 Задати акцію",
                    callback_data=f"ls:a_promo:{product_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Зняти акцію",
                    callback_data=f"ls:a_promo_clear:{product_id}",
                )
            ],
        ]
    )