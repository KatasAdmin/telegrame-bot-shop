from __future__ import annotations

from typing import Any

from aiogram import Bot

from rent_platform.modules.telegram_shop.repo.support_links import TelegramShopSupportLinksRepo


def _normalize_url(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""

    # @channel -> https://t.me/channel
    if s.startswith("@"):
        return f"https://t.me/{s[1:]}"

    # email -> mailto:
    if "@" in s and "://" not in s and "t.me/" not in s and not s.startswith("mailto:"):
        return f"mailto:{s}"

    # bare domain -> https://
    if "://" not in s and (s.startswith("t.me/") or "." in s):
        return "https://" + s

    return s


def _kb_url(rows: list[list[tuple[str, str]]]) -> dict:
    """
    rows: [[(title, url)], ...]
    """
    return {"inline_keyboard": [[{"text": t, "url": u} for (t, u) in row] for row in rows]}


async def send_support_menu(bot: Bot, chat_id: int, tenant_id: str, *, is_admin: bool) -> None:
    await TelegramShopSupportLinksRepo.ensure_defaults(tenant_id)

    items = await TelegramShopSupportLinksRepo.list_enabled(tenant_id)
    # announce_chat_id НЕ показуємо юзеру
    items = [x for x in (items or []) if str(x.get("key") or "") != "announce_chat_id"]

    if not items:
        txt = (
            "🆘 *Підтримка*\n\n"
            "Поки що немає активних контактів.\n"
        )
        if is_admin:
            txt += "\n_Адмін: відкрий /a → Підтримка і увімкни кнопки._"
        await bot.send_message(chat_id, txt, parse_mode="Markdown")
        return

    rows: list[list[tuple[str, str]]] = []
    for it in items:
        title = str(it.get("title") or "").strip() or "Контакт"
        url = _normalize_url(str(it.get("url") or ""))
        if not url:
            continue
        rows.append([(title, url)])

    text = "🆘 *Підтримка*\n\nОбери як з нами звʼязатися 👇"
    await bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=_kb_url(rows))