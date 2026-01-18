# rent_platform/modules/shop_bot.py
from __future__ import annotations

import logging
from typing import Any

from aiogram import Bot

log = logging.getLogger(__name__)


async def handle_update(tenant: dict, update: dict, bot: Bot) -> bool:
    """
    Демка продукту shop_bot.
    Поки просто відповідає на /start та текст "ping".
    Повертає True якщо апдейт оброблено.
    """
    try:
        msg = (update.get("message") or {})
        text = (msg.get("text") or "").strip()
        chat = msg.get("chat") or {}
        chat_id = chat.get("id")

        if not chat_id:
            return False

        if text == "/start":
            await bot.send_message(chat_id, "🛒 Це Shop Bot (demo). Пиши: ping")
            return True

        if text.lower() == "ping":
            await bot.send_message(chat_id, "pong ✅")
            return True

        return False

    except Exception as e:
        log.exception("shop_bot handle_update failed: %s", e)
        return False