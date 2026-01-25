from __future__ import annotations

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def user_main_kb() -> ReplyKeyboardMarkup:
    # тільки для юзера — максимум просто і красиво
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛍 Каталог"), KeyboardButton(text="🛒 Кошик")],
            [KeyboardButton(text="ℹ️ Допомога")],
        ],
        resize_keyboard=True,
        selective=True,
        one_time_keyboard=False,
    )


def back_to_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🏠 Меню")]],
        resize_keyboard=True,
        selective=True,
        one_time_keyboard=False,
    )