from __future__ import annotations

from typing import Any

from aiogram import Bot

from rent_platform.modules.telegram_shop.repo.support_links import TelegramShopSupportLinksRepo
from rent_platform.modules.telegram_shop.repo.products import ProductsRepo


async def maybe_post_new_product(bot: Bot, tenant_id: str, product_id: int) -> bool:
    """
    Публікує пост у канал (якщо увімкнено).
    Налаштування:
      - support_links.key='announce_chat_id' => url має бути числом chat_id (наприклад: -1001234567890)
      - enabled=1 щоб працювало
    """
    cfg = await TelegramShopSupportLinksRepo.get(tenant_id, "announce_chat_id")
    if not cfg or int(cfg.get("enabled") or 0) != 1:
        return False

    raw = str(cfg.get("url") or "").strip()
    if not raw:
        return False

    try:
        channel_chat_id = int(raw)
    except Exception:
        return False

    p = await ProductsRepo.get_active(tenant_id, product_id)
    if not p:
        return False

    name = str(p.get("name") or "").strip()
    desc = str(p.get("description") or "").strip()
    price_kop = int(p.get("price_kop") or 0)

    text = f"🆕 *Новинка!*\n\n🛍 *{name}*\n💰 {price_kop/100:.2f} грн\n"
    if desc:
        text += f"\n{desc}"

    cover_file_id = await ProductsRepo.get_cover_photo_file_id(tenant_id, int(p["id"]))
    if cover_file_id:
        await bot.send_photo(channel_chat_id, photo=cover_file_id, caption=text, parse_mode="Markdown")
    else:
        await bot.send_message(channel_chat_id, text, parse_mode="Markdown")

    return True