from __future__ import annotations

from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)


# ---------- USER UI ----------

def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛍 Каталог"), KeyboardButton(text="🛒 Кошик")],
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


def products_list_kb(products: list[dict]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for p in products:
        rows.append(
            [InlineKeyboardButton(text=f"➕ {p['name']}", callback_data=f"ls:add:{p['id']}")]
        )
    rows.append([InlineKeyboardButton(text="🛒 Відкрити кошик", callback_data="ls:cart")])
    rows.append([InlineKeyboardButton(text="🏠 Меню", callback_data="ls:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_card_kb(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➖", callback_data=f"ls:dec:{product_id}"),
                InlineKeyboardButton(text="➕", callback_data=f"ls:inc:{product_id}"),
                InlineKeyboardButton(text="🗑", callback_data=f"ls:del:{product_id}"),
            ],
            [InlineKeyboardButton(text="🛒 Кошик", callback_data="ls:cart")],
            [InlineKeyboardButton(text="⬅️ Назад до каталогу", callback_data="ls:products")],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="ls:menu")],
        ]
    )


def cart_kb(has_items: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    rows.append([InlineKeyboardButton(text="🔄 Оновити", callback_data="ls:cart")])

    if has_items:
        rows.append([InlineKeyboardButton(text="✅ Оформити замовлення", callback_data="ls:checkout")])
        rows.append([InlineKeyboardButton(text="🧹 Очистити кошик", callback_data="ls:cart_clear")])

    rows.append([InlineKeyboardButton(text="🛍 Каталог", callback_data="ls:products")])
    rows.append([InlineKeyboardButton(text="🏠 Меню", callback_data="ls:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------- ADMIN UI ----------
# (щоб імпорт не падав + база для адмінки)

def admin_kb() -> ReplyKeyboardMarkup:
    """
    Мінімальна адмін-клава. Можеш показувати її тільки адмінам.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Додати товар"), KeyboardButton(text="📦 Товари")],
            [KeyboardButton(text="🔥 Хіти"), KeyboardButton(text="🎁 Акції")],
            [KeyboardButton(text="🏠 Меню")],
        ],
        resize_keyboard=True,
        selective=True,
    )


def admin_menu_kb() -> InlineKeyboardMarkup:
    """
    Інлайн-адмін меню (на майбутнє).
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Додати товар", callback_data="ls:a:add_product")],
            [InlineKeyboardButton(text="📦 Список товарів", callback_data="ls:a:products")],
            [
                InlineKeyboardButton(text="🔥 Хіти", callback_data="ls:a:hits"),
                InlineKeyboardButton(text="🎁 Акції", callback_data="ls:a:promos"),
            ],
        ]
    )