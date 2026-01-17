# rent_platform/modules/core/router.py
from __future__ import annotations

from typing import Any

from aiogram import Bot

from rent_platform.shared.utils import send_message
from rent_platform.core.tenant_ctx import Tenant


def _extract_chat_id(update: dict[str, Any]) -> int | None:
    msg = update.get("message")
    if msg and msg.get("chat", {}).get("id") is not None:
        return int(msg["chat"]["id"])

    cq = update.get("callback_query")
    if cq:
        m = cq.get("message")
        if m and m.get("chat", {}).get("id") is not None:
            return int(m["chat"]["id"])

    return None


def _extract_text(update: dict[str, Any]) -> str:
    msg = update.get("message") or {}
    text = msg.get("text") or ""
    return str(text)


async def handle_update(tenant: Tenant, update: dict[str, Any]) -> bool:
    """
    Core-модуль: базові команди tenant-бота.
    Повертає True якщо обробив update.
    """
    text = _extract_text(update).strip()
    if not text:
        return False

    if text not in ("/start", "/help"):
        return False

    chat_id = _extract_chat_id(update)
    if chat_id is None:
        return False

    bot = Bot(token=tenant.bot_token)
    try:
        mods = ", ".join(tenant.active_modules) if tenant.active_modules else "—"
        msg = (
            "✅ *Tenant bot активний*\n\n"
            f"🆔 Bot ID: `{tenant.id}`\n"
            f"🧩 Активні модулі: *{mods}*\n\n"
            "Команди:\n"
            "• /start — старт\n"
            "• /help — допомога\n\n"
            "_Далі підключимо UI модулів (shop/support/…)._\n"
        )
        await send_message(bot, chat_id, msg, parse_mode="Markdown")
    finally:
        await bot.session.close()

    return True