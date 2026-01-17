# rent_platform/modules/shop/router.py

from rent_platform.modules.shop.storage import get_shop_db
from rent_platform.shared.utils import send_message


async def handle_update(tenant, update: dict) -> bool:
    message = update.get("message")
    if not message:
        return False

    text = message.get("text", "")
    chat_id = message["chat"]["id"]

    db = get_shop_db(tenant.tenant_id)

    # --- старт магазину ---
    if text == "/shop":
        await send_message(
            tenant.bot_token,
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
            await send_message(tenant.bot_token, chat_id, "Товарів ще немає 😅")
            return True

        lines = ["📦 <b>Товари:</b>"]
        for p in db["products"]:
            lines.append(f"• {p['name']} — {p['price']} грн")

        await send_message(tenant.bot_token, chat_id, "\n".join(lines))
        return True

    return False