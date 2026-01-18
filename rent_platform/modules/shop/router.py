# rent_platform/modules/shop/router.py
from __future__ import annotations

from aiogram import Bot

from rent_platform.modules.shop.storage import get_shop_db
from rent_platform.shared.utils import send_message


async def handle_update(tenant: dict, update: dict, bot: Bot) -> bool:
    """
    Tenant module handler contract:
      - tenant: dict з БД (id, bot_token, secret, ...)
      - update: raw telegram update dict
      - bot: готовий aiogram.Bot для цього tenant-а
    Return True якщо апдейт оброблено модулем.
    """
    message = update.get("message")
    if not message:
        return False

    text = (message.get("text") or "").strip()
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if not chat_id:
        return False

    tenant_id = tenant.get("id")  # в БД поле tenants.id
    db = get_shop_db(tenant_id)

    # --- старт магазину ---
    if text == "/shop":
        await send_message(
            bot,
            chat_id,
            "🛒 <b>Ласкаво просимо в магазин!</b>\n\n"
            "Команди:\n"
            "/products — товари\n"
            "/orders — мої замовлення",
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

    # (на майбутнє) --- список замовлень ---
    if text == "/orders":
        if not db["orders"]:
            await send_message(bot, chat_id, "Замовлень ще немає 🙂")
            return True
        await send_message(bot, chat_id, f"🧾 Замовлень: {len(db['orders'])}")
        return True

    return False