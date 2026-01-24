# rent_platform/modules/shop_bot/router.py
from __future__ import annotations

from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from rent_platform.modules.shop_bot.storage import get_shop_db, get_user_state
from rent_platform.modules.shop_bot.ui import main_menu_kb, back_to_menu_kb, hits_menu_kb
from rent_platform.shared.utils import send_message


async def _show_or_edit(bot: Bot, chat_id: int, user_state, text: str, kb=None) -> None:
    """
    “Переливання”: якщо маємо last_msg_id — редагуємо, інакше шлемо нове.
    """
    if user_state.last_msg_id:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=user_state.last_msg_id,
                text=text,
                parse_mode="HTML",
                reply_markup=kb,
            )
            return
        except TelegramBadRequest:
            # якщо не можна відредагувати (старе/видалене) — падаємо на send
            pass

    msg = await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=kb)
    user_state.last_msg_id = msg.message_id


async def handle_update(tenant: Any, update: dict, bot: Bot) -> bool:
    message = update.get("message")
    callback = update.get("callback_query")

    db = get_shop_db(str(tenant.id))

    # ---------- MESSAGE ----------
    if message:
        text = (message.get("text") or "").strip()
        chat_id = (message.get("chat") or {}).get("id")
        user_id = (message.get("from") or {}).get("id")
        if not chat_id or not user_id:
            return False

        st = get_user_state(db, int(user_id))

        if text in ("/start", "/shop"):
            await _show_or_edit(
                bot,
                chat_id,
                st,
                "🛒 <b>Магазин</b>\n\nОбери розділ 👇",
                kb=main_menu_kb(),
            )
            return True

        # поки як заглушки, але щоб було “живе”
        if text == "/products":
            await _show_or_edit(bot, chat_id, st, "📦 <b>Каталог</b>\n\n(поки порожньо)", kb=back_to_menu_kb())
            return True

        if text == "/orders":
            await _show_or_edit(bot, chat_id, st, "🧾 <b>Історія замовлень</b>\n\n(поки порожньо)", kb=back_to_menu_kb())
            return True

        if text == "/ping":
            await send_message(bot, chat_id, "pong ✅")
            return True

        if text == "/help":
            await send_message(bot, chat_id, "Команди: /shop /products /orders /ping")
            return True

        return False

    # ---------- CALLBACK ----------
    if callback:
        data = (callback.get("data") or "").strip()
        msg = callback.get("message") or {}
        chat_id = (msg.get("chat") or {}).get("id")
        user_id = (callback.get("from") or {}).get("id")
        cb_id = callback.get("id")
        if not chat_id or not user_id or not cb_id:
            return False

        st = get_user_state(db, int(user_id))

        # підтвердити “крутилку”
        try:
            await bot.answer_callback_query(cb_id)
        except Exception:
            pass

        if data == "shop:menu":
            await _show_or_edit(bot, chat_id, st, "🛒 <b>Магазин</b>\n\nОбери розділ 👇", kb=main_menu_kb())
            return True

        if data == "shop:catalog":
            await _show_or_edit(bot, chat_id, st, "📦 <b>Каталог</b>\n\nКатегорії з’являться після додавання в адмінці.", kb=back_to_menu_kb())
            return True

        if data == "shop:cart":
            await _show_or_edit(bot, chat_id, st, "🛒 <b>Кошик</b>\n\nПоки порожньо. Додай товар з каталогу.", kb=back_to_menu_kb())
            return True

        if data == "shop:hits":
            await _show_or_edit(bot, chat_id, st, "🔥 <b>Хіти / Акції</b>\n\nОбери розділ 👇", kb=hits_menu_kb())
            return True

        if data in ("shop:hits:list", "shop:deals:list"):
            title = "🔥 Хіти" if data == "shop:hits:list" else "🏷 Акції"
            await _show_or_edit(bot, chat_id, st, f"{title}\n\n(поки порожньо — заповниш з адмінки)", kb=back_to_menu_kb())
            return True

        if data == "shop:fav":
            await _show_or_edit(bot, chat_id, st, "❤️ <b>Обране</b>\n\nПоки порожньо.", kb=back_to_menu_kb())
            return True

        if data == "shop:orders":
            await _show_or_edit(bot, chat_id, st, "🧾 <b>Історія замовлень</b>\n\nПоки порожньо.", kb=back_to_menu_kb())
            return True

        if data == "shop:support":
            support_text = (db.get("support") or {}).get("text") or "📞 Підтримка"
            await _show_or_edit(bot, chat_id, st, f"🆘 <b>Підтримка</b>\n\n{support_text}", kb=back_to_menu_kb())
            return True

        return False

    return False