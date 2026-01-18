from __future__ import annotations

from aiogram import Bot

from rent_platform.shared.utils import send_message


def _extract_message(update: dict) -> dict | None:
    # підтримка message + callback_query.message
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


def _welcome_text() -> str:
    return (
        "✅ <b>Орендований бот активний</b>\n\n"
        "Доступні команди:\n"
        "• /shop — магазин\n"
        "• /products — список товарів\n"
        "• /orders — мої замовлення\n\n"
        "Сервісні:\n"
        "• /ping — перевірка звʼязку\n"
        "• /help — підказка\n"
    )


async def handle_update(tenant: dict, update: dict, bot: Bot) -> bool:
    msg = _extract_message(update)
    if not msg:
        return False

    chat_id = _extract_chat_id(msg)
    if not chat_id:
        return False

    text = _extract_text(update)

    # --- базові команди ---
    if text in ("/start", "/help"):
        await send_message(bot, chat_id, _welcome_text())
        return True

    if text == "/ping":
        await send_message(bot, chat_id, "pong ✅")
        return True

    # --- fallback: якщо користувач пише щось незрозуміле ---
    # (але не перехоплюємо команди інших модулів типу /shop, /products — їх обробить shop)
    if text and text.startswith("/") and text not in ("/shop", "/products", "/orders"):
        await send_message(
            bot,
            chat_id,
            "Не знаю цю команду 🤝\n\n" + _welcome_text(),
        )
        return True

    return False