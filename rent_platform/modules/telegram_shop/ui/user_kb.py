from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def _kb(rows: list[list[str]], *, resize: bool = True) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t) for t in row] for row in rows],
        resize_keyboard=resize,
    )


def main_menu_kb(*, is_admin: bool = False) -> ReplyKeyboardMarkup:
    """
    Головне меню для покупця.
    is_admin залишив, щоб не падало якщо роутер передає цей аргумент.
    """
    rows = [
        ["🛍 Каталог", "🛒 Кошик"],
        ["🔥 Хіти / Акції", "⭐ Обране"],
        ["🧾 Історія замовлень", "🆘 Підтримка"],
    ]
    if is_admin:
        rows.insert(0, ["🛠 Адмінка"])
    return _kb(rows)


def catalog_kb(*, is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        ["🛒 Кошик", "⭐ Обране"],
        ["🔥 Хіти / Акції", "🧾 Історія замовлень"],
        ["⬅️ Меню"],
    ]
    if is_admin:
        rows.insert(0, ["🛠 Адмінка"])
    return _kb(rows)


def cart_kb(*, is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        ["✅ Оформити замовлення"],
        ["🧹 Очистити кошик"],
        ["⬅️ Меню"],
    ]
    if is_admin:
        rows.insert(0, ["🛠 Адмінка"])
    return _kb(rows)


def favorites_kb(*, is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        ["🛍 Каталог", "🛒 Кошик"],
        ["⬅️ Меню"],
    ]
    if is_admin:
        rows.insert(0, ["🛠 Адмінка"])
    return _kb(rows)


def orders_history_kb(*, is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        ["🛍 Каталог", "🛒 Кошик"],
        ["⬅️ Меню"],
    ]
    if is_admin:
        rows.insert(0, ["🛠 Адмінка"])
    return _kb(rows)


def support_kb(*, is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        ["🛍 Каталог", "🛒 Кошик"],
        ["⬅️ Меню"],
    ]
    if is_admin:
        rows.insert(0, ["🛠 Адмінка"])
    return _kb(rows)