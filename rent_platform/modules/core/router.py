from __future__ import annotations

from aiogram import Bot
from rent_platform.shared.utils import send_message


async def handle_update(tenant: dict, update: dict, bot: Bot) -> bool:
    msg = update.get("message")
    if not msg:
        return False

    text = (msg.get("text") or "").strip()
    chat_id = (msg.get("chat") or {}).get("id")
    if not chat_id:
        return False

    if text == "/start":
        await send_message(
            bot,
            chat_id,
            "✅ <b>Орендований бот активний</b>\n\n"
            "Команди:\n"
            "/shop — магазин\n"
            "/products — товари\n"
            "/orders — замовлення",
        )
        return True

    return False