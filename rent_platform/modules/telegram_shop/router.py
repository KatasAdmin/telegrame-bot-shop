from __future__ import annotations

import logging
from typing import Any

from aiogram import Bot
from aiogram.types import Update, Message

from rent_platform.modules.telegram_shop.ui.user_kb import (
    main_menu_kb,
    catalog_kb,
    cart_kb,
    favorites_kb,
    orders_history_kb,
    support_kb,
)

log = logging.getLogger(__name__)

# --- Тексти кнопок (однаково з ui/user_kb.py) ---
BTN_CATALOG = "🛍 Каталог"
BTN_CART = "🛒 Кошик"
BTN_HITS = "🔥 Хіти / Акції"
BTN_FAV = "⭐ Обране"
BTN_ORDERS = "🧾 Історія замовлень"
BTN_SUPPORT = "🆘 Підтримка"
BTN_MENU_BACK = "⬅️ Меню"
BTN_ADMIN = "🛠 Адмінка"


async def _send_or_edit_menu(bot: Bot, chat_id: int, text: str, *, is_admin: bool) -> None:
    await bot.send_message(chat_id, text, reply_markup=main_menu_kb(is_admin=is_admin))


async def _show_catalog(bot: Bot, chat_id: int, *, is_admin: bool) -> None:
    await bot.send_message(
        chat_id,
        "🛍 *Каталог*\n\nТут буде список товарів. (Поки що в розробці)",
        parse_mode="Markdown",
        reply_markup=catalog_kb(is_admin=is_admin),
    )


async def _show_cart(bot: Bot, chat_id: int, *, is_admin: bool) -> None:
    await bot.send_message(
        chat_id,
        "🛒 *Кошик*\n\nПоки що порожньо або в розробці.",
        parse_mode="Markdown",
        reply_markup=cart_kb(is_admin=is_admin),
    )


async def _show_hits(bot: Bot, chat_id: int, *, is_admin: bool) -> None:
    await bot.send_message(
        chat_id,
        "🔥 *Хіти / Акції*\n\nТут будуть хіти та акційні товари. (Поки що в розробці)",
        parse_mode="Markdown",
        reply_markup=catalog_kb(is_admin=is_admin),
    )


async def _show_favorites(bot: Bot, chat_id: int, *, is_admin: bool) -> None:
    await bot.send_message(
        chat_id,
        "⭐ *Обране*\n\nТут буде список обраних товарів. (Поки що в розробці)",
        parse_mode="Markdown",
        reply_markup=favorites_kb(is_admin=is_admin),
    )


async def _show_orders_history(bot: Bot, chat_id: int, *, is_admin: bool) -> None:
    await bot.send_message(
        chat_id,
        "🧾 *Історія замовлень*\n\nТут буде історія твоїх замовлень. (Поки що в розробці)",
        parse_mode="Markdown",
        reply_markup=orders_history_kb(is_admin=is_admin),
    )


async def _show_support(bot: Bot, chat_id: int, *, is_admin: bool) -> None:
    await bot.send_message(
        chat_id,
        "🆘 *Підтримка*\n\nНапиши сюди своє питання і ми додамо канал підтримки.\n(Поки що в розробці)",
        parse_mode="Markdown",
        reply_markup=support_kb(is_admin=is_admin),
    )


def _extract_message(update: dict) -> dict | None:
    return update.get("message") or update.get("edited_message")


def _get_text(msg: dict) -> str:
    return (msg.get("text") or "").strip()


def _get_chat_id(msg: dict) -> int:
    return int(msg["chat"]["id"])


def _get_user_id(msg: dict) -> int:
    return int(msg["from"]["id"])


def _is_admin_stub(user_id: int) -> bool:
    # Поки що заглушка. Потім підвʼяжемо до tenant-налаштувань / списку адмінів.
    return False


async def handle_update(tenant: dict, data: dict[str, Any], bot: Bot) -> bool:
    """
    Entry-point модуля для tenant-ботів.
    Повертає True якщо апдейт обробили.
    """
    msg = _extract_message(data)
    if not msg:
        return False

    text = _get_text(msg)
    if not text:
        return False

    chat_id = _get_chat_id(msg)
    user_id = _get_user_id(msg)
    is_admin = _is_admin_stub(user_id)

    # Команди
    if text in ("/start", "/shop"):
        await _send_or_edit_menu(
            bot,
            chat_id,
            "🛒 *Магазин*\n\nОбирай розділ кнопками нижче 👇",
            is_admin=is_admin,
        )
        return True

    # Кнопки меню
    if text == BTN_CATALOG:
        await _show_catalog(bot, chat_id, is_admin=is_admin)
        return True

    if text == BTN_CART:
        await _show_cart(bot, chat_id, is_admin=is_admin)
        return True

    if text == BTN_HITS:
        await _show_hits(bot, chat_id, is_admin=is_admin)
        return True

    if text == BTN_FAV:
        await _show_favorites(bot, chat_id, is_admin=is_admin)
        return True

    if text == BTN_ORDERS:
        await _show_orders_history(bot, chat_id, is_admin=is_admin)
        return True

    if text == BTN_SUPPORT:
        await _show_support(bot, chat_id, is_admin=is_admin)
        return True

    if text == BTN_MENU_BACK:
        await _send_or_edit_menu(
            bot,
            chat_id,
            "⬅️ Повернув у меню 👇",
            is_admin=is_admin,
        )
        return True

    # Адмін-кнопка (поки без логіки)
    if text == BTN_ADMIN and is_admin:
        await bot.send_message(chat_id, "🛠 Адмінка (поки що в розробці)", reply_markup=main_menu_kb(is_admin=True))
        return True

    return False