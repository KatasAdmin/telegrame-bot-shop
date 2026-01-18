from __future__ import annotations

from aiogram import Bot

from rent_platform.modules.shop.storage import get_shop_db
from rent_platform.shared.utils import send_message


async def handle_update(tenant: dict, update: dict, bot: Bot) -> bool:
    message = update.get("message")
    if not message:
        return False

    text = (message.get("text") or "").strip()
    chat_id = (message.get("chat") or {}).get("id")
    if not chat_id:
        return False

    db = get_shop_db(tenant["id"])  # ✅ tenant id тепер в dict

    # --- старт магазину ---
    if text == "/shop":
        await send_message(
            bot,
            chat_id,
            "🛒 <b>Ласкаво просимо в магазин!</b>\n\n"
            "Команди:\n"
            "/products — товари\n"
            "/orders — мої замовлення"
        )
        return True

    # --- список товарів ---
    if text == "/products":
        if not db["products"]:
            await send_message(bot, chat_id, "Товарів ще немає 😅")
            return True

        lines = ["📦 <b>Товари:</b>"]
        for p in db["products"]:
            lines.append(f"• {p['name']} — {p['price']} грн")

        await send_message(bot, chat_id, "\n".join(lines))
        return True

    # --- замовлення (заглушка) ---
    if text == "/orders":
        if not db["orders"]:
            await send_message(bot, chat_id, "Замовлень ще немає 🙂")
            return True

    return False