from __future__ import annotations

import time
from typing import Any

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from rent_platform.core.tenant_ctx import Tenant
from rent_platform.modules.shop.storage import get_shop_db
from rent_platform.modules.shop.ui import send_or_edit, main_menu_kb


async def handle_update(tenant: Tenant, update: dict[str, Any], bot: Bot) -> bool:
    message = update.get("message")
    callback = update.get("callback_query")

    db = get_shop_db(tenant.id)

    # -----------------------
    # Message flow
    # -----------------------
    if message:
        text = (message.get("text") or "").strip()
        chat_id = (message.get("chat") or {}).get("id")
        if not chat_id:
            return False

        if text in ("/start", "/shop"):
            await send_or_edit(
                bot,
                chat_id,
                "🛒 <b>Ласкаво просимо в магазин!</b>\n\nОбери розділ нижче 👇",
                kb=main_menu_kb(),
            )
            return True

        # залишимо команди для дебага
        if text == "/products":
            # тимчасовий список (поки без карток)
            if not db["products"]:
                await bot.send_message(chat_id, "Товарів ще немає 😅", parse_mode="HTML")
                return True
            lines = ["📦 <b>Товари:</b>"]
            for p in db["products"]:
                lines.append(f"• {p['title']} — {p['price_uah']} грн")
            await bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML")
            return True

        return False

    # -----------------------
    # Callback flow (6 кнопок)
    # -----------------------
    if callback:
        data = (callback.get("data") or "").strip()
        msg = callback.get("message") or {}
        chat_id = (msg.get("chat") or {}).get("id")
        message_id = msg.get("message_id")
        if not chat_id or not message_id:
            return False

        # ACK callback щоб “крутилка” не висіла
        try:
            await bot.answer_callback_query(callback_query_id=callback["id"])
        except Exception:
            pass

        if data == "shop:catalog":
            # поки заглушка
            await send_or_edit(
                bot,
                chat_id,
                "🛍 <b>Каталог</b>\n\n(Далі: категорії → картки товарів)",
                message_id=int(message_id),
                kb=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ В меню", callback_data="shop:menu")]
                ]),
            )
            return True

        if data == "shop:cart":
            await send_or_edit(
                bot,
                chat_id,
                "🛒 <b>Кошик</b>\n\n(Далі: список товарів + qty ➖ ➕ 🗑 + сума)",
                message_id=int(message_id),
                kb=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ В меню", callback_data="shop:menu")]
                ]),
            )
            return True

        if data == "shop:fav":
            await send_or_edit(
                bot,
                chat_id,
                "⭐️ <b>Обране</b>\n\n(Далі: список обраних товарів)",
                message_id=int(message_id),
                kb=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ В меню", callback_data="shop:menu")]
                ]),
            )
            return True

        if data == "shop:hits":
            await send_or_edit(
                bot,
                chat_id,
                "🔥 <b>Хіти / Акції</b>\n\n(Далі: перемикач Хіти або Акції)",
                message_id=int(message_id),
                kb=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ В меню", callback_data="shop:menu")]
                ]),
            )
            return True

        if data == "shop:support":
            st = db["settings"]["support_text"]
            await send_or_edit(
                bot,
                chat_id,
                f"🆘 <b>Підтримка</b>\n\n{st}",
                message_id=int(message_id),
                kb=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ В меню", callback_data="shop:menu")]
                ]),
            )
            return True

        if data == "shop:orders":
            await send_or_edit(
                bot,
                chat_id,
                "📜 <b>Історія замовлень</b>\n\n(Далі: список замовлень + деталі)",
                message_id=int(message_id),
                kb=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ В меню", callback_data="shop:menu")]
                ]),
            )
            return True

        if data == "shop:menu":
            await send_or_edit(
                bot,
                chat_id,
                "🛒 <b>Меню магазину</b>\n\nОбери розділ нижче 👇",
                message_id=int(message_id),
                kb=main_menu_kb(),
            )
            return True

        return False

    return False