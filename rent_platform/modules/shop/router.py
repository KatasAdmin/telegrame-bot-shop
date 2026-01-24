from __future__ import annotations

from aiogram import Bot

from rent_platform.core.tenant_ctx import Tenant
from rent_platform.modules.shop.storage import get_shop_db
from rent_platform.shared.utils import send_message


async def handle_update(tenant: Tenant, update: dict, bot: Bot) -> bool:
    """
    MVP router магазину.
    Пізніше перепишемо під 6 кнопок, каталог/категорії/картки/кошик/обране/історію.
    """
    message = update.get("message")
    if not message:
        return False

    text = (message.get("text") or "").strip()
    chat_id = (message.get("chat") or {}).get("id")
    if not chat_id:
        return False

    db = get_shop_db(tenant.id)

    if text in ("/start", "/shop"):
        await send_message(
            bot,
            chat_id,
            "🛒 <b>Ласкаво просимо в магазин!</b>\n\n"
            "Команди (MVP):\n"
            "/products — товари\n"
            "/orders — мої замовлення\n\n"
            "Далі зробимо меню з 6 кнопок 😉",
        )
        return True

    if text == "/products":
        products = db.get("products") or []
        if not products:
            await send_message(bot, chat_id, "Товарів ще немає 😅")
            return True

        lines = ["📦 <b>Товари:</b>"]
        for p in products:
            lines.append(f"• <b>{p['name']}</b> — {p['price']} грн")
            if p.get("desc"):
                lines.append(f"  {p['desc']}")

        await send_message(bot, chat_id, "\n".join(lines))
        return True

    if text == "/orders":
        orders = db.get("orders") or []
        if not orders:
            await send_message(bot, chat_id, "Замовлень ще немає 🙂")
            return True

        lines = ["🧾 <b>Мої замовлення:</b>"]
        for o in orders:
            lines.append(f"• #{o.get('id')} — {o.get('total')} грн")
        await send_message(bot, chat_id, "\n".join(lines))
        return True

    return False