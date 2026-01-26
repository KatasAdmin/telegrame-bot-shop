from __future__ import annotations

import time
from typing import Any

from aiogram import Bot
from aiogram.types import InputMediaPhoto

from rent_platform.modules.telegram_shop.repo.products import ProductsRepo
from rent_platform.modules.telegram_shop.repo.favorites import TelegramShopFavoritesRepo
from rent_platform.modules.telegram_shop.ui.inline_kb import favorites_card_kb
from rent_platform.modules.telegram_shop.ui.user_kb import favorites_kb

try:
    from rent_platform.modules.telegram_shop.repo.categories import CategoriesRepo  # type: ignore
except Exception:  # pragma: no cover
    CategoriesRepo = None  # type: ignore


def _fmt_money(kop: int) -> str:
    kop = int(kop or 0)
    uah = kop // 100
    cents = kop % 100
    return f"{uah}.{cents:02d} грн"


def _promo_active(p: dict[str, Any], now: int) -> bool:
    pp = int(p.get("promo_price_kop") or 0)
    pu = int(p.get("promo_until_ts") or 0)
    return pp > 0 and (pu == 0 or pu > now)


def _fmt_dt(ts: int) -> str:
    import datetime as _dt
    return _dt.datetime.fromtimestamp(int(ts)).strftime("%d.%m.%Y %H:%M")


def _effective_price_kop(p: dict[str, Any], now: int) -> int:
    return int(p.get("promo_price_kop") or 0) if _promo_active(p, now) else int(p.get("price_kop") or 0)


async def _get_category_title(tenant_id: str, category_id: int | None) -> str:
    if not category_id or category_id <= 0:
        return "Без категорії"

    # пробуємо CategoriesRepo.get_by_id / get / etc без жорсткої залежності
    if CategoriesRepo is not None:
        for meth in ("get_by_id", "get", "get_one"):
            fn = getattr(CategoriesRepo, meth, None)
            if fn:
                try:
                    row = await fn(tenant_id, int(category_id))  # type: ignore[misc]
                    if row and row.get("name"):
                        return str(row["name"])
                except Exception:
                    pass

    return f"Категорія #{int(category_id)}"


async def _build_fav_card(tenant_id: str, user_id: int, product_id: int) -> dict | None:
    p = await ProductsRepo.get_active(tenant_id, product_id)
    if not p:
        return None

    now = int(time.time())

    pid = int(p["id"])
    name = str(p["name"])
    base_price = int(p.get("price_kop") or 0)
    desc = (p.get("description") or "").strip()

    promo_on = _promo_active(p, now)
    promo_until = int(p.get("promo_until_ts") or 0)
    eff = _effective_price_kop(p, now)

    cat_title = await _get_category_title(tenant_id, int(p.get("category_id") or 0) or None)

    prev_pid = await TelegramShopFavoritesRepo.get_prev(tenant_id, user_id, pid)
    next_pid = await TelegramShopFavoritesRepo.get_next(tenant_id, user_id, pid)

    cover = await ProductsRepo.get_cover_photo_file_id(tenant_id, pid)

    text = f"⭐ *Обране*\n\n🛍 *{name}*\nКатегорія: _{cat_title}_\n\n"

    if promo_on:
        until_txt = "без кінця" if promo_until == 0 else _fmt_dt(promo_until)
        text += (
            f"🔥 *АКЦІЯ!*\n"
            f"Було: {_fmt_money(base_price)}\n"
            f"Зараз: *{_fmt_money(eff)}*\n"
            f"До: {until_txt}\n"
        )
    else:
        text += f"Ціна: *{_fmt_money(base_price)}*\n"

    if desc:
        text += f"\n{desc}"

    kb = favorites_card_kb(
        product_id=pid,
        has_prev=bool(prev_pid),
        has_next=bool(next_pid),
    )

    return {
        "pid": pid,
        "has_photo": bool(cover),
        "file_id": cover,
        "text": text,
        "kb": kb,
        "prev_pid": prev_pid,
        "next_pid": next_pid,
    }


async def send_favorites(bot: Bot, chat_id: int, tenant_id: str, user_id: int, *, is_admin: bool) -> None:
    first = await TelegramShopFavoritesRepo.get_first(tenant_id, user_id)
    if not first:
        await bot.send_message(
            chat_id,
            "⭐ *Обране*\n\nПоки що порожньо.",
            parse_mode="Markdown",
            reply_markup=favorites_kb(is_admin=is_admin),
        )
        return

    card = await _build_fav_card(tenant_id, user_id, int(first))
    if not card:
        await bot.send_message(
            chat_id,
            "⭐ *Обране*\n\nПоки що порожньо.",
            parse_mode="Markdown",
            reply_markup=favorites_kb(is_admin=is_admin),
        )
        return

    if card["has_photo"]:
        await bot.send_photo(
            chat_id,
            photo=card["file_id"],
            caption=card["text"],
            parse_mode="Markdown",
            reply_markup=card["kb"],
        )
    else:
        await bot.send_message(
            chat_id,
            card["text"],
            parse_mode="Markdown",
            reply_markup=card["kb"],
        )


async def _edit_fav_card(
    bot: Bot,
    chat_id: int,
    message_id: int,
    tenant_id: str,
    user_id: int,
    product_id: int,
) -> bool:
    card = await _build_fav_card(tenant_id, user_id, product_id)
    if not card:
        return False

    if card["has_photo"]:
        media = InputMediaPhoto(media=card["file_id"], caption=card["text"], parse_mode="Markdown")
        await bot.edit_message_media(
            chat_id=chat_id,
            message_id=message_id,
            media=media,
            reply_markup=card["kb"],
        )
    else:
        await bot.edit_message_text(
            card["text"],
            chat_id=chat_id,
            message_id=message_id,
            parse_mode="Markdown",
            reply_markup=card["kb"],
        )
    return True


async def handle_favorites_callback(
    *,
    bot: Bot,
    tenant_id: str,
    user_id: int,
    chat_id: int,
    message_id: int,
    payload: str,
) -> bool:
    if not payload.startswith("tgfav:"):
        return False

    parts = payload.split(":")
    action = parts[1] if len(parts) > 1 else ""

    if action == "noop":
        return True

    if action == "back":
        # просто перевідкриємо першу картку (без списків)
        await send_favorites(bot, chat_id, tenant_id, user_id, is_admin=False)
        return True

    if action in ("prev", "next", "rm"):
        pid_raw = parts[2] if len(parts) > 2 else "0"
        pid = int(pid_raw) if pid_raw.isdigit() else 0
        if pid <= 0:
            return True

        if action == "rm":
            await TelegramShopFavoritesRepo.remove(tenant_id, user_id, pid)
            # після видалення — покажемо наступний доступний
            first = await TelegramShopFavoritesRepo.get_first(tenant_id, user_id)
            if not first:
                await bot.edit_message_text(
                    "⭐ *Обране*\n\nПоки що порожньо.",
                    chat_id=chat_id,
                    message_id=message_id,
                    parse_mode="Markdown",
                    reply_markup=None,
                )
                return True
            await _edit_fav_card(bot, chat_id, message_id, tenant_id, user_id, int(first))
            return True

        if action == "prev":
            prev_pid = await TelegramShopFavoritesRepo.get_prev(tenant_id, user_id, pid)
            if prev_pid:
                await _edit_fav_card(bot, chat_id, message_id, tenant_id, user_id, int(prev_pid))
            return True

        if action == "next":
            next_pid = await TelegramShopFavoritesRepo.get_next(tenant_id, user_id, pid)
            if next_pid:
                await _edit_fav_card(bot, chat_id, message_id, tenant_id, user_id, int(next_pid))
            return True

    return True