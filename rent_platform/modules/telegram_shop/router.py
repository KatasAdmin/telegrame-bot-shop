# rent_platform/modules/telegram_shop/router.py
from __future__ import annotations

from aiogram import Bot

from rent_platform.modules.telegram_shop.manifest import MANIFEST
from rent_platform.modules.telegram_shop.storage import get_shop_db
from rent_platform.shared.utils import send_message


def _is_admin(tenant: dict, user_id: int) -> bool:
    # простий варіант: owner_user_id == user_id
    try:
        return int(tenant.get("owner_user_id") or 0) == int(user_id)
    except Exception:
        return False


async def handle_update(tenant: dict, update: dict, bot: Bot) -> bool:
    message = update.get("message")
    if not message:
        return False

    text = (message.get("text") or "").strip()
    chat_id = (message.get("chat") or {}).get("id")
    user_id = (message.get("from") or {}).get("id")
    if not chat_id:
        return False

    db = get_shop_db(tenant["id"])

    # --- help / menu ---
    if text in ("/shop", "🛒 Магазин"):
        await send_message(
            bot,
            chat_id,
            "🛒 <b>Телеграм магазин</b>\n\n"
            "Команди:\n"
            "• /products — товари\n"
            "• /orders — мої замовлення\n",
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
        await send_message(bot, chat_id, "Є замовлення (пізніше зробимо список).")
        return True

    # --- адмін: підказка ---
    if text == "/a_help":
        if not _is_admin(tenant, int(user_id or 0)):
            await send_message(bot, chat_id, "⛔️ Це адмін-команда.")
            return True

        cmds = "\n".join([f"• {c} — {d}" for c, d in MANIFEST.get("commands", [])])
        await send_message(bot, chat_id, f"🛠 <b>Адмін-команди</b>\n\n{cmds}")
        return True

    # --- адмін: додати товар (простий формат) ---
    # /a_add_product Назва | 123
    if text.startswith("/a_add_product"):
        if not _is_admin(tenant, int(user_id or 0)):
            await send_message(bot, chat_id, "⛔️ Це адмін-команда.")
            return True

        raw = text[len("/a_add_product"):].strip()
        if "|" not in raw:
            await send_message(bot, chat_id, "Формат: <code>/a_add_product Назва | 123</code>")
            return True

        name, price_s = [x.strip() for x in raw.split("|", 1)]
        try:
            price = int(price_s)
        except Exception:
            await send_message(bot, chat_id, "Ціна має бути числом. Формат: <code>123</code>")
            return True

        db["products"].append({"name": name[:64], "price": price})
        await send_message(bot, chat_id, f"✅ Додано: <b>{name}</b> — {price} грн")
        return True

    return False