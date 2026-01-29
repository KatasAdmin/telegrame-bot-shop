from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

# --- Single source of truth for button texts ---
BTN_CATALOG = "🛍 Каталог"
BTN_CART = "🛒 Кошик"
BTN_HITS = "🔥 Хіти / Акції"
BTN_FAV = "⭐ Обране"
BTN_ORDERS = "🧾 Історія замовлень"
BTN_SUPPORT = "🆘 Підтримка"
BTN_MENU_BACK = "⬅️ Меню"

BTN_ADMIN = "🛠 Адмінка"
BTN_ADMIN_ORDERS = "🧾 Замовлення"
BTN_ADMIN_INTEGRATIONS = "⚙️ Інтеграції"  # NEW

BTN_CHECKOUT = "✅ Оформити замовлення"
BTN_CLEAR_CART = "🧹 Очистити кошик"


def _kb(rows: list[list[str]], *, resize: bool = True) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t) for t in row] for row in rows],
        resize_keyboard=resize,
    )


def _admin_rows() -> list[list[str]]:
    # 2 рядки, щоб не було “каші” в одному рядку
    return [
        [BTN_ADMIN, BTN_ADMIN_ORDERS],
        [BTN_ADMIN_INTEGRATIONS],
    ]


def main_menu_kb(*, is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [BTN_CATALOG, BTN_CART],
        [BTN_HITS, BTN_FAV],
        [BTN_ORDERS, BTN_SUPPORT],
    ]
    if is_admin:
        rows = _admin_rows() + rows
    return _kb(rows)


def catalog_kb(*, is_admin: bool = False) -> ReplyKeyboardMarkup:
    """
    В каталозі не дублюємо "Кошик", бо він і так є в головному меню.
    Лишаємо мінімум навігації.
    """
    rows = [
        [BTN_FAV, BTN_HITS],
        [BTN_ORDERS],
        [BTN_MENU_BACK],
    ]
    if is_admin:
        rows = _admin_rows() + rows
    return _kb(rows)


def cart_kb(*, is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [BTN_CHECKOUT],
        [BTN_CLEAR_CART],
        [BTN_MENU_BACK],
    ]
    if is_admin:
        rows = _admin_rows() + rows
    return _kb(rows)


def favorites_kb(*, is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [BTN_CATALOG, BTN_CART],
        [BTN_MENU_BACK],
    ]
    if is_admin:
        rows = _admin_rows() + rows
    return _kb(rows)


def orders_history_kb(*, is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [BTN_CATALOG, BTN_CART],
        [BTN_MENU_BACK],
    ]
    if is_admin:
        rows = _admin_rows() + rows
    return _kb(rows)


def support_kb(*, is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [BTN_CATALOG, BTN_CART],
        [BTN_MENU_BACK],
    ]
    if is_admin:
        rows = _admin_rows() + rows
    return _kb(rows)