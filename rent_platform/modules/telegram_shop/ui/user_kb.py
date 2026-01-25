from __future__ import annotations

from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


def main_menu_kb(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = [
        [KeyboardButton(text="🛍 Каталог"), KeyboardButton(text="ℹ️ Допомога")],
    ]
    if is_admin:
        rows.append([KeyboardButton(text="🛠 Адмін")])

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        selective=True,
    )


def catalog_kb(products: list[dict]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for p in products:
        pid = int(p.get("id", 0))
        name = str(p.get("name", "Товар"))
        rows.append(
            [InlineKeyboardButton(text=f"🧾 {name}", callback_data=f"ts:product:{pid}")]
        )

    rows.append([InlineKeyboardButton(text="🏠 Меню", callback_data="ts:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_card_kb(product_id: int) -> InlineKeyboardMarkup:
    pid = int(product_id)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад до каталогу", callback_data="ts:catalog")],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="ts:menu")],
        ]
    )