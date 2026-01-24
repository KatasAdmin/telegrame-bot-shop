from __future__ import annotations

from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)


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
        rows.append([InlineKeyboardButton(text=f"➕ {p['name']}", callback_data=f"ls:add:{p['id']}")])
    rows.append([InlineKeyboardButton(text="🛒 Відкрити кошик", callback_data="ls:cart")])
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
        ]
    )


def cart_kb(has_items: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    rows.append([InlineKeyboardButton(text="🔄 Оновити", callback_data="ls:cart")])

    if has_items:
        rows.append([InlineKeyboardButton(text="✅ Оформити замовлення", callback_data="ls:checkout")])
        rows.append([InlineKeyboardButton(text="🧹 Очистити кошик", callback_data="ls:cart_clear")])

    rows.append([InlineKeyboardButton(text="🛍 Каталог", callback_data="ls:products")])
    return InlineKeyboardMarkup(inline_keyboard=rows)