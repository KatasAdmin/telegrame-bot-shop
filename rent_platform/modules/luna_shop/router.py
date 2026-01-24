# rent_platform/modules/luna_shop/router.py
from __future__ import annotations

from aiogram import Bot

from rent_platform.core.tenant_ctx import Tenant
from rent_platform.modules.luna_shop.storage import get_shop_db
from rent_platform.modules.luna_shop.ui import start_text, shop_menu_text
from rent_platform.shared.utils import send_message


def _get_message(update: dict) -> dict | None:
    msg = update.get("message")
    if isinstance(msg, dict):
        return msg
    return None


def _get_chat_id(message: dict) -> int | None:
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    try:
        return int(chat_id)
    except Exception:
        return None


def _get_text(message: dict) -> str:
    return (message.get("text") or "").strip()


async def handle_update(tenant: Tenant, update: dict) -> bool:
    """
    Module handler signature: (tenant, update) -> bool
    True якщо обробили апдейт.
    """
    message = _get_message(update)
    if not message:
        return False

    chat_id = _get_chat_id(message)
    if not chat_id:
        return False

    text = _get_text(message)
    if not text:
        return False

    bot = Bot(token=tenant.bot_token)
    try:
        # --- service ---
        if text == "/ping":
            await send_message(bot, chat_id, "pong ✅")
            return True

        if text in ("/help",):
            await send_message(bot, chat_id, start_text())
            return True

        # --- start / main ---
        if text in ("/start",):
            await send_message(bot, chat_id, start_text())
            return True

        if text == "/shop":
            await send_message(bot, chat_id, shop_menu_text())
            return True

        # --- products ---
        if text == "/products":
            db = get_shop_db(tenant.id)

            products = db.get("products") or []
            if not products:
                await send_message(bot, chat_id, "Товарів ще немає 😅\n\n(Додай адмін-командою /a_addprod)")
                return True

            lines = ["📦 <b>Товари:</b>"]
            for p in products:
                name = p.get("name") or "Без назви"
                price = int(p.get("price") or 0)
                lines.append(f"• {name} — {price} грн")

            await send_message(bot, chat_id, "\n".join(lines))
            return True

        # --- orders (stub) ---
        if text == "/orders":
            db = get_shop_db(tenant.id)
            orders = db.get("orders") or []
            if not orders:
                await send_message(bot, chat_id, "Замовлень ще немає 🙂")
                return True

            await send_message(bot, chat_id, "📦 Замовлення є, але показ ще в розробці 🙂")
            return True

        # --- admin: super simple for testing (in-memory) ---
        # формат:
        # /a_addprod Назва | 123
        if text.startswith("/a_addprod"):
            raw = text.removeprefix("/a_addprod").strip()
            if not raw:
                await send_message(bot, chat_id, "Формат: /a_addprod Назва товару | 123")
                return True

            if "|" not in raw:
                await send_message(bot, chat_id, "Формат: /a_addprod Назва товару | 123")
                return True

            name_part, price_part = [x.strip() for x in raw.split("|", 1)]
            try:
                price = int(price_part)
            except Exception:
                await send_message(bot, chat_id, "Ціна має бути числом. Формат: /a_addprod Назва | 123")
                return True

            db = get_shop_db(tenant.id)
            db["products"].append({"name": name_part[:128], "price": max(0, price)})

            await send_message(bot, chat_id, f"✅ Додано товар: <b>{name_part}</b> — {price} грн")
            return True

        return False

    finally:
        await bot.session.close()