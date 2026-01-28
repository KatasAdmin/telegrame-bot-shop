# -*- coding: utf-8 -*-
from __future__ import annotations

from aiogram import Bot

from rent_platform.modules.telegram_shop.repo.support_links import TelegramShopSupportLinksRepo


def _normalize_url(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""

    # numeric chat_id is not clickable for users -> hide it
    if s.lstrip("-").isdigit():
        return ""

    # @channel / @manager -> https://t.me/channel
    if s.startswith("@"):
        return f"https://t.me/{s[1:]}"

    low = s.lower()

    # already has scheme
    if "://" in low or low.startswith("mailto:") or low.startswith("tg://"):
        return s

    # email -> mailto:
    if "@" in s and "t.me/" not in low:
        return f"mailto:{s}"

    # t.me/... without scheme
    if low.startswith("t.me/"):
        return "https://" + s

    # bare domain -> https://
    if "." in s:
        return "https://" + s

    return s


def _kb_url(rows: list[list[tuple[str, str]]]) -> dict:
    """
    rows: [[(title, url)], ...]
    """
    return {"inline_keyboard": [[{"text": t, "url": u} for (t, u) in row] for row in rows]}


async def send_support_menu(bot: Bot, chat_id: int, tenant_id: str, *, is_admin: bool) -> None:
    # ensure defaults exist for tenant
    await TelegramShopSupportLinksRepo.ensure_defaults(tenant_id)

    items = await TelegramShopSupportLinksRepo.list_enabled(tenant_id) or []

    # do not show internal announce_chat_id to users
    items = [x for x in items if str(x.get("key") or "") != "announce_chat_id"]

    if not items:
        txt = "🆘 *Підтримка*\n\nПоки що немає активних контактів."
        if is_admin:
            txt += "\n\n_Адмін: відкрий /a → Підтримка і увімкни кнопки._"
        await bot.send_message(chat_id, txt, parse_mode="Markdown")
        return

    rows: list[list[tuple[str, str]]] = []
    for it in items:
        title = (str(it.get("title") or "").strip() or "Контакт")[:64]
        url = _normalize_url(str(it.get("url") or ""))
        if not url:
            continue
        rows.append([(title, url)])

    if not rows:
        txt = "🆘 *Підтримка*\n\nКонтакти ще не налаштовані 😅"
        if is_admin:
            txt += "\n\n_Адмін: відкрий /a → Підтримка і задай значення._"
        await bot.send_message(chat_id, txt, parse_mode="Markdown")
        return

    text = "🆘 *Підтримка*\n\nОбери як з нами звʼязатися 👇"
    await bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=_kb_url(rows))