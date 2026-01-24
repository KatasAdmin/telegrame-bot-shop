from __future__ import annotations

from aiogram import Bot

from rent_platform.shared.utils import send_message


def _get_chat_id(update: dict) -> int | None:
    msg = update.get("message") or {}
    chat = msg.get("chat") or {}
    cid = chat.get("id")
    return int(cid) if cid is not None else None


def _get_text(update: dict) -> str:
    msg = update.get("message") or {}
    return (msg.get("text") or "").strip()


def _is_admin(tenant: dict, user_id: int) -> bool:
    # мінімально: owner_user_id з tenant
    return int(tenant.get("owner_user_id") or 0) == int(user_id)


async def handle_update(tenant: dict, update: dict, bot: Bot) -> bool:
    text = _get_text(update)
    if not text:
        return False

    chat_id = _get_chat_id(update)
    if not chat_id:
        return False

    msg = update.get("message") or {}
    user = msg.get("from") or {}
    user_id = int(user.get("id") or 0)

    # user меню
    if text == "/shop":
        await send_message(
            bot,
            chat_id,
            "🛒 <b>Меню магазину</b>\n"
            "• /products — товари\n"
            "• /orders — мої замовлення"
        )
        return True

    if text == "/products":
        await send_message(bot, chat_id, "Товарів ще немає 😅 (додай через /a_add_product)")
        return True

    if text == "/orders":
        await send_message(bot, chat_id, "Замовлень ще немає 🙂")
        return True

    # admin
    if text == "/a_help":
        if not _is_admin(tenant, user_id):
            await send_message(bot, chat_id, "⛔️ Тільки для адміна.")
            return True
        await send_message(
            bot,
            chat_id,
            "🛠 <b>Адмін-команди</b>\n"
            "• /a_add_product — додати товар (скоро зробимо)\n"
        )
        return True

    if text.startswith("/a_add_product"):
        if not _is_admin(tenant, user_id):
            await send_message(bot, chat_id, "⛔️ Тільки для адміна.")
            return True
        await send_message(bot, chat_id, "Ок, далі зробимо покрокове додавання товару ✅")
        return True

    return False