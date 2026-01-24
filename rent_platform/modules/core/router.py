from __future__ import annotations

from aiogram import Bot

from rent_platform.shared.utils import send_message
from rent_platform.core.product_loader import (
    get_active_product_key,
    load_product_welcome,
)


def _extract_message(update: dict) -> dict | None:
    msg = update.get("message")
    if msg:
        return msg
    cb = update.get("callback_query")
    if cb and cb.get("message"):
        return cb["message"]
    return None


def _extract_text(update: dict) -> str:
    msg = update.get("message")
    if msg and msg.get("text"):
        return (msg.get("text") or "").strip()

    cb = update.get("callback_query")
    if cb and cb.get("data"):
        return (cb.get("data") or "").strip()

    return ""


def _extract_chat_id(msg: dict) -> int | None:
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    return int(chat_id) if chat_id is not None else None


def _base_welcome_text() -> str:
    return (
        "✅ <b>Орендований бот активний</b>\n\n"
        "Сервісні:\n"
        "• /ping — перевірка звʼязку\n"
        "• /help — підказка\n"
    )


async def _send_welcome(bot: Bot, chat_id: int, tenant: dict) -> None:
    # База
    text = _base_welcome_text()

    # Продуктовий блок
    pk = get_active_product_key(tenant)
    if pk:
        get_welcome = load_product_welcome(pk)
        if get_welcome:
            try:
                text = get_welcome(tenant) + "\n\n" + _base_welcome_text()
            except Exception:
                # якщо welcome продукта впав — не валимо /start
                pass

    await send_message(bot, chat_id, text)


async def handle_update(tenant: dict, update: dict, bot: Bot) -> bool:
    msg = _extract_message(update)
    if not msg:
        return False

    chat_id = _extract_chat_id(msg)
    if not chat_id:
        return False

    text = _extract_text(update)

    if text in ("/start", "/help"):
        await _send_welcome(bot, chat_id, tenant)
        return True

    if text == "/ping":
        await send_message(bot, chat_id, "pong ✅")
        return True

    # якщо хтось вводить ліву команду — підкажемо
    if text and text.startswith("/") and text not in ("/start", "/help", "/ping"):
        await send_message(bot, chat_id, "Не знаю цю команду 🤝\n\n" + _base_welcome_text())
        return True

    return False