# rent_platform/modules/shop_bot/ui.py
from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Каталог", callback_data="shop:catalog")],
        [InlineKeyboardButton(text="🛒 Кошик", callback_data="shop:cart")],
        [InlineKeyboardButton(text="🔥 Хіти/Акції", callback_data="shop:hits")],
        [InlineKeyboardButton(text="❤️ Обране", callback_data="shop:fav")],
        [InlineKeyboardButton(text="🧾 Історія замовлень", callback_data="shop:orders")],
        [InlineKeyboardButton(text="🆘 Підтримка", callback_data="shop:support")],
    ])


def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="shop:menu")]
    ])


def hits_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 Хіти", callback_data="shop:hits:list")],
        [InlineKeyboardButton(text="🏷 Акції", callback_data="shop:deals:list")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="shop:menu")],
    ])