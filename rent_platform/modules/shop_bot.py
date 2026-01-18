from __future__ import annotations

from aiogram.types import Update

from rent_platform.core.registry import register_module


@register_module("shop_bot")
async def shop_bot_module(tenant: dict, raw_update: dict, bot) -> bool:
    # працюємо тільки для купленого продукту Luna Shop
    if tenant.get("product_key") != "shop_bot":
        return False

    upd = Update.model_validate(raw_update)

    if upd.message and upd.message.text:
        chat_id = upd.message.chat.id
        text = (upd.message.text or "").strip().lower()

        if text in ("/start", "старт", "меню"):
            await bot.send_message(
                chat_id,
                "🛒 *Luna Shop Bot*\n\n"
                "Це демо-магазин (MVP). Команди:\n"
                "• /catalog — каталог\n"
                "• /cart — кошик\n"
                "• /help — підтримка\n",
                parse_mode="Markdown",
            )
            return True

        if text == "/catalog":
            await bot.send_message(chat_id, "📦 Каталог (демо):\n1) Товар А — 100 грн\n2) Товар B — 200 грн")
            return True

        if text == "/cart":
            await bot.send_message(chat_id, "🧺 Кошик порожній (демо).")
            return True

        if text == "/help":
            await bot.send_message(chat_id, "🆘 Підтримка (демо): Напиши, що треба.")
            return True

    return False