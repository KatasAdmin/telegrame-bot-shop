from __future__ import annotations

from aiogram import Bot
from rent_platform.shared.utils import send_message


def _extract_message(update: dict) -> dict | None:
    msg = update.get("message")
    if msg:
        return msg
    cb = update.get("callback_query")
    if cb and cb.get("message"):
        return cb["message"]
    return None


def _extract_chat_id(msg: dict) -> int | None:
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    return int(chat_id) if chat_id is not None else None


def _normalize_command(text: str) -> str:
    """
    /shop@TestBot  -> /shop
    /shop 123      -> /shop
    """
    t = (text or "").strip()
    if not t:
        return ""
    first = t.split(maxsplit=1)[0]          # беремо перший токен
    if "@" in first:
        first = first.split("@", 1)[0]      # відрізаємо @username
    return first


def _extract_text(update: dict) -> str:
    msg = update.get("message")
    if msg and msg.get("text"):
        return (msg.get("text") or "").strip()

    cb = update.get("callback_query")
    if cb and cb.get("data"):
        return (cb.get("data") or "").strip()

    return ""


def _welcome_text() -> str:
    return (
        "✅ <b>Орендований бот активний</b>\n\n"
        "Сервісні команди:\n"
        "• /ping — перевірка звʼязку\n"
        "• /help — підказка\n\n"
        "ℹ️ Магазин відкривається через меню кнопками або командою /shop"
    )


async def handle_update(tenant: dict, update: dict, bot: Bot) -> bool:
    msg = _extract_message(update)
    if not msg:
        return False

    chat_id = _extract_chat_id(msg)
    if not chat_id:
        return False

    text = _extract_text(update)
    cmd = _normalize_command(text)

    # core обробляє тільки свої
    if cmd in ("/start", "/help"):
        await send_message(bot, chat_id, _welcome_text())
        return True

    if cmd == "/ping":
        await send_message(bot, chat_id, "pong ✅")
        return True

    # ⚠️ ВАЖЛИВО:
    # будь-які інші команди НЕ перехоплюємо — хай обробляє продукт (luna_shop)
    if cmd.startswith("/"):
        return False

    # якщо це просто текст (не команда) — теж не чіпаємо, хай продукт вирішує
    return False