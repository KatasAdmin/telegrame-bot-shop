# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import time
from typing import Any

from aiogram import Bot
from aiogram.types import InputMediaPhoto

from rent_platform.modules.telegram_shop.user_support import send_support_menu
from rent_platform.modules.telegram_shop.admin import admin_handle_update, is_admin_user
from rent_platform.modules.telegram_shop.admin_orders import admin_orders_send_menu

from rent_platform.modules.telegram_shop.repo.products import ProductsRepo
from rent_platform.modules.telegram_shop.repo.cart import TelegramShopCartRepo
from rent_platform.modules.telegram_shop.repo.favorites import TelegramShopFavoritesRepo
from rent_platform.modules.telegram_shop.repo.support_links import TelegramShopSupportLinksRepo

from rent_platform.modules.telegram_shop.ui.user_kb import (
    main_menu_kb,
    catalog_kb,
    support_kb,
    BTN_CATALOG,
    BTN_CART,
    BTN_HITS,
    BTN_FAV,
    BTN_ORDERS,
    BTN_SUPPORT,
    BTN_MENU_BACK,
    BTN_ADMIN_ORDERS,
    BTN_ADMIN,
    BTN_CHECKOUT,
    BTN_CLEAR_CART,
)

from rent_platform.modules.telegram_shop.ui.inline_kb import catalog_categories_kb

from rent_platform.modules.telegram_shop.user_cart import (
    send_cart,
    handle_cart_message,
    handle_cart_callback,
)
from rent_platform.modules.telegram_shop.user_favorites import (
    send_favorites,
    handle_favorites_callback,
)
from rent_platform.modules.telegram_shop.user_orders import (
    send_orders_list,
    handle_orders_callback,
)

try:
    from rent_platform.modules.telegram_shop.repo.categories import CategoriesRepo  # type: ignore
except Exception:  # pragma: no cover
    CategoriesRepo = None  # type: ignore

log = logging.getLogger(__name__)

# =========================================================
# Admin "edit value" state (simple pending input)
# pending[(tenant_id, user_id)] = {"key": str, "ts": int}
# =========================================================
_PENDING_SUPPORT_EDIT: dict[tuple[str, int], dict[str, Any]] = {}


# =========================================================
# basic helpers
# =========================================================
def _extract_message(update: dict) -> dict | None:
    return update.get("message") or update.get("edited_message")


def _extract_callback(update: dict) -> dict | None:
    return update.get("callback_query")


def _normalize_text(s: str) -> str:
    s = (s or "").strip()
    s = s.replace("\ufe0f", "").replace("\u200d", "")
    s = " ".join(s.split())
    return s


def _get_text(msg: dict) -> str:
    return _normalize_text((msg.get("text") or ""))


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


def _kb(rows: list[list[tuple[str, str]]]) -> dict:
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for (t, d) in row] for row in rows]}


def _kb_url(rows: list[list[tuple[str, str]]]) -> dict:
    return {"inline_keyboard": [[{"text": t, "url": u} for (t, u) in row] for row in rows]}


def _product_kb(
    *,
    scope: str,  # "cat" | "promo" | "hit"
    product_id: int,
    has_prev: bool,
    has_next: bool,
    category_id: int | None,
    is_fav: bool,
) -> dict:
    cid = int(category_id or 0)
    sc = (scope or "cat").strip() or "cat"

    if sc == "promo":
        prev_action, next_action = "pprev", "pnext"
        cats_action = "pcats"
    elif sc == "hit":
        prev_action, next_action = "hprev", "hnext"
        cats_action = "hcats"
    else:
        prev_action, next_action = "prev", "next"
        cats_action = ""

    nav_row: list[tuple[str, str]] = [
        ("⬅️", f"tgshop:{prev_action}:{product_id}:{cid}:{sc}") if has_prev else ("·", "tgshop:noop:0:0:0"),
        ("➡️", f"tgshop:{next_action}:{product_id}:{cid}:{sc}") if has_next else ("·", "tgshop:noop:0:0:0"),
    ]

    fav_txt = "⭐ Прибрати" if is_fav else "⭐ В обране"
    rows: list[list[tuple[str, str]]] = [
        nav_row,
        [
            ("🛒 Додати", f"tgshop:add:{product_id}:{cid}:{sc}"),
            (fav_txt, f"tgshop:fav:{product_id}:{cid}:{sc}"),
        ],
    ]

    if cats_action:
        rows.append([("📁 Категорії", f"tgshop:{cats_action}:0:0:{sc}")])

    return _kb(rows)


async def _send_menu(bot: Bot, chat_id: int, text: str, *, is_admin: bool) -> None:
    await bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=main_menu_kb(is_admin=is_admin))


# =========================================================
# Support (user view) - залишив, хоч ти юзаєш send_support_menu
# =========================================================
async def _send_support(bot: Bot, chat_id: int, tenant_id: str, *, is_admin: bool) -> None:
    await TelegramShopSupportLinksRepo.ensure_defaults(tenant_id)

    links = await TelegramShopSupportLinksRepo.list_enabled(tenant_id)
    rows: list[list[tuple[str, str]]] = []

    for item in links:
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        if not title or not url:
            continue
        rows.append([(title, url)])

    if not rows:
        await bot.send_message(
            chat_id,
            "🆘 *Підтримка*\n\nКонтакти ще не налаштовані 😅",
            parse_mode="Markdown",
            reply_markup=support_kb(is_admin=is_admin),
        )
        return

    await bot.send_message(
        chat_id,
        "🆘 *Підтримка*\n\nОберіть, куди написати 👇",
        parse_mode="Markdown",
        reply_markup=_kb_url(rows),
    )


# =========================================================
# Support (admin view)
# =========================================================
def _support_admin_kb(items: list[dict[str, Any]]) -> dict:
    rows: list[list[tuple[str, str]]] = []
    for it in items:
        key = str(it["key"])
        title = str(it.get("title") or key)
        enabled = bool(int(it.get("enabled") or 0))
        flag = "✅" if enabled else "⛔"
        rows.append([(f"{flag} {title}", f"tgsupadm:toggle:{key}")])
        rows.append([("✏️ Змінити значення", f"tgsupadm:edit:{key}")])
    rows.append([("⬅️ Назад", "tgsupadm:back:0")])
    return _kb(rows)


async def _send_support_admin(bot: Bot, chat_id: int, tenant_id: str) -> None:
    await TelegramShopSupportLinksRepo.ensure_defaults(tenant_id)
    items = await TelegramShopSupportLinksRepo.list_all(tenant_id)
    await bot.send_message(
        chat_id,
        "🆘 *Адмін — Підтримка*\n\n"
        "Тут можна:\n"
        "• вкл/викл кнопки\n"
        "• змінювати посилання/контакти\n\n"
        "Натисни дію 👇",
        parse_mode="Markdown",
        reply_markup=_support_admin_kb(items),
    )


# =========================================================
# Catalog categories
# =========================================================
async def _send_categories_menu(bot: Bot, chat_id: int, tenant_id: str, *, is_admin: bool) -> None:
    if CategoriesRepo is None:
        await bot.send_message(
            chat_id,
            "🛍 *Каталог*\n\nКатегорії ще не підключені.",
            parse_mode="Markdown",
            reply_markup=catalog_kb(is_admin=is_admin),
        )
        return

    await CategoriesRepo.ensure_default(tenant_id)  # type: ignore[misc]
    await CategoriesRepo.ensure_show_all_flag(tenant_id)  # type: ignore[misc]

    include_all = await CategoriesRepo.is_show_all_enabled(tenant_id)  # type: ignore[misc]
    cats = await CategoriesRepo.list_public(tenant_id, limit=50)  # type: ignore[misc]

    if not cats and not include_all:
        await bot.send_message(
            chat_id,
            "🛍 *Каталог*\n\nПоки що немає категорій.",
            parse_mode="Markdown",
            reply_markup=catalog_kb(is_admin=is_admin),
        )
        return

    await bot.send_message(
        chat_id,
        "🛍 *Каталог*\n\nОбери категорію 👇",
        parse_mode="Markdown",
        reply_markup=catalog_categories_kb(cats, include_all=bool(include_all)),
    )


# =========================================================
# Hits / Promos menus
# =========================================================
async def _send_hits_promos_entry(bot: Bot, chat_id: int, *, is_admin: bool) -> None:
    kb = _kb([[("🔥 Акції", "tgshop:pcats:0:0:promo"), ("⭐ Хіти", "tgshop:hcats:0:0:hit")]])
    await bot.send_message(
        chat_id,
        "🔥 *Хіти / Акції*\n\n"
        "Обери режим 👇\n\n"
        "• *Акції* — товари з активною знижкою 🔥\n"
        "• *Хіти* — найпопулярніші / рекомендовані товари ⭐\n",
        parse_mode="Markdown",
        reply_markup=kb,
    )


async def _send_scope_categories(bot: Bot, chat_id: int, tenant_id: str, *, scope: str) -> None:
    if CategoriesRepo is None:
        await bot.send_message(chat_id, "🔥 *Хіти / Акції*\n\nКатегорії ще не підключені.", parse_mode="Markdown")
        return

    await CategoriesRepo.ensure_default(tenant_id)  # type: ignore[misc]
    cats_all = await CategoriesRepo.list_public(tenant_id, limit=100)  # type: ignore[misc]

    if scope == "promo":
        ids = await ProductsRepo.list_promo_category_ids(tenant_id)
        ids_set = set(ids or [])
        title = "🔥 *Акції*"
        empty_txt = "Немає акційних товарів 😅"
        action = "pcat"
        back_scope = "promo"
    else:
        ids = await ProductsRepo.list_hit_category_ids(tenant_id)
        ids_set = set(ids or [])
        title = "⭐ *Хіти*"
        empty_txt = "Немає хітів 😅"
        action = "hcat"
        back_scope = "hit"

    cats = [c for c in (cats_all or []) if int(c.get("id") or 0) in ids_set]

    if not cats:
        await bot.send_message(chat_id, f"{title}\n\n{empty_txt}", parse_mode="Markdown")
        return

    rows: list[list[tuple[str, str]]] = []
    for c in cats:
        cid = int(c["id"])
        name = str(c.get("name") or "").strip()
        if not name:
            continue
        rows.append([(f"📁 {name}", f"tgshop:{action}:0:{cid}:{back_scope}")])

    rows.append([("⬅️ Назад", "tgshop:hp:0:0:0")])

    await bot.send_message(chat_id, f"{title}\n\nОбери категорію 👇", parse_mode="Markdown", reply_markup=_kb(rows))


# =========================================================
# Product card rendering
# =========================================================
async def _build_product_card(
    tenant_id: str,
    user_id: int,
    product_id: int,
    *,
    category_id: int | None,
    scope: str,
) -> dict | None:
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
    effective_price = _effective_price_kop(p, now)

    if scope == "cat":
        prev_p = await ProductsRepo.get_prev_active(tenant_id, pid, category_id=category_id)
        next_p = await ProductsRepo.get_next_active(tenant_id, pid, category_id=category_id)
    elif scope == "promo":
        prev_p = await ProductsRepo.get_prev_promo_active(tenant_id, pid, category_id=category_id)
        next_p = await ProductsRepo.get_next_promo_active(tenant_id, pid, category_id=category_id)
    else:
        prev_p = await ProductsRepo.get_prev_hit_active(tenant_id, pid, category_id=category_id)
        next_p = await ProductsRepo.get_next_hit_active(tenant_id, pid, category_id=category_id)

    cover_file_id = await ProductsRepo.get_cover_photo_file_id(tenant_id, pid)

    badge = "🔥 " if scope == "promo" else ("⭐ " if scope == "hit" else "")
    text = f"{badge}🛍 *{name}*\n\n"

    if promo_on:
        until_txt = "без кінця" if promo_until == 0 else _fmt_dt(promo_until)
        text += (
            f"🔥 *АКЦІЯ!*\n"
            f"Було: {_fmt_money(base_price)}\n"
            f"Зараз: *{_fmt_money(effective_price)}*\n"
            f"До: {until_txt}\n"
        )
    else:
        text += f"Ціна: *{_fmt_money(base_price)}*\n"

    text += f"ID: `{pid}`"
    if desc:
        text += f"\n\n{desc}"

    is_fav = await TelegramShopFavoritesRepo.is_fav(tenant_id, user_id, pid)

    kb = _product_kb(
        scope=scope,
        product_id=pid,
        has_prev=bool(prev_p),
        has_next=bool(next_p),
        category_id=category_id,
        is_fav=bool(is_fav),
    )

    return {"has_photo": bool(cover_file_id), "file_id": cover_file_id, "text": text, "kb": kb}


async def _send_first_product_card(
    bot: Bot,
    chat_id: int,
    tenant_id: str,
    user_id: int,
    *,
    is_admin: bool,
    category_id: int | None,
    scope: str,
) -> None:
    if scope == "cat":
        first = await ProductsRepo.get_first_active(tenant_id, category_id=category_id)
    elif scope == "promo":
        first = await ProductsRepo.get_first_promo_active(tenant_id, category_id=category_id)
    else:
        first = await ProductsRepo.get_first_hit_active(tenant_id, category_id=category_id)

    if not first:
        if scope == "cat":
            await bot.send_message(chat_id, "🛍 *Каталог*\n\nПоки що немає товарів у цій категорії.", parse_mode="Markdown")
            await _send_categories_menu(bot, chat_id, tenant_id, is_admin=is_admin)
        elif scope == "promo":
            await bot.send_message(chat_id, "🔥 *Акції*\n\nУ цій категорії немає акційних товарів.", parse_mode="Markdown")
            await _send_scope_categories(bot, chat_id, tenant_id, scope="promo")
        else:
            await bot.send_message(chat_id, "⭐ *Хіти*\n\nУ цій категорії немає хітів.", parse_mode="Markdown")
            await _send_scope_categories(bot, chat_id, tenant_id, scope="hit")
        return

    card = await _build_product_card(tenant_id, user_id, int(first["id"]), category_id=category_id, scope=scope)
    if not card:
        await bot.send_message(chat_id, "Поки що порожньо 😅", parse_mode="Markdown")
        return

    if card["has_photo"]:
        await bot.send_photo(chat_id, photo=card["file_id"], caption=card["text"], parse_mode="Markdown", reply_markup=card["kb"])
    else:
        await bot.send_message(chat_id, card["text"], parse_mode="Markdown", reply_markup=card["kb"])


async def _edit_product_card(
    bot: Bot,
    chat_id: int,
    message_id: int,
    tenant_id: str,
    user_id: int,
    product_id: int,
    *,
    category_id: int | None,
    scope: str,
) -> bool:
    card = await _build_product_card(tenant_id, user_id, product_id, category_id=category_id, scope=scope)
    if not card:
        return False

    if card["has_photo"]:
        media = InputMediaPhoto(media=card["file_id"], caption=card["text"], parse_mode="Markdown")
        await bot.edit_message_media(media=media, chat_id=chat_id, message_id=message_id, reply_markup=card["kb"])
    else:
        await bot.edit_message_text(card["text"], chat_id=chat_id, message_id=message_id, parse_mode="Markdown", reply_markup=card["kb"])
    return True


async def _edit_product_kb_only(
    bot: Bot,
    chat_id: int,
    message_id: int,
    tenant_id: str,
    user_id: int,
    product_id: int,
    *,
    category_id: int | None,
    scope: str,
) -> None:
    card = await _build_product_card(tenant_id, user_id, product_id, category_id=category_id, scope=scope)
    if not card:
        return
    await bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=card["kb"])


# =========================================================
# Main entry
# =========================================================
async def handle_update(tenant: dict, data: dict[str, Any], bot: Bot) -> bool:
    tenant_id = str(tenant["id"])

    # --- callbacks ---
    cb = _extract_callback(data)
    if cb:
        payload = (cb.get("data") or "").strip()
        chat_id = int(cb["message"]["chat"]["id"])
        user_id = int(cb["from"]["id"])
        is_admin = is_admin_user(tenant=tenant, user_id=user_id)
        cb_id = cb.get("id")
        msg_id = int(cb["message"]["message_id"])

        # A) Support admin callbacks
        if payload.startswith("tgsupadm:"):
            if not is_admin:
                if cb_id:
                    await bot.answer_callback_query(cb_id, text="⛔ Нема доступу", show_alert=False)
                return True

            parts = payload.split(":")
            action = parts[1] if len(parts) > 1 else ""
            key = parts[2] if len(parts) > 2 else ""

            if action == "back":
                await admin_orders_send_menu(bot, chat_id)
                if cb_id:
                    await bot.answer_callback_query(cb_id)
                return True

            if action == "toggle" and key:
                await TelegramShopSupportLinksRepo.toggle(tenant_id, key)
                items = await TelegramShopSupportLinksRepo.list_all(tenant_id)
                await bot.edit_message_reply_markup(chat_id=chat_id, message_id=msg_id, reply_markup=_support_admin_kb(items))
                if cb_id:
                    await bot.answer_callback_query(cb_id, text="✅ Оновлено", show_alert=False)
                return True

            if action == "edit" and key:
                _PENDING_SUPPORT_EDIT[(tenant_id, user_id)] = {"key": key, "ts": int(time.time())}
                cur = await TelegramShopSupportLinksRepo.get(tenant_id, key)
                cur_url = (cur or {}).get("url") or ""
                await bot.send_message(
                    chat_id,
                    "✏️ *Зміна значення*\n\n"
                    f"Ключ: `{key}`\n"
                    f"Поточне: `{cur_url}`\n\n"
                    "Надішли нове значення одним повідомленням.\n"
                    "Скасувати: `/cancel`",
                    parse_mode="Markdown",
                )
                if cb_id:
                    await bot.answer_callback_query(cb_id)
                return True

            if cb_id:
                await bot.answer_callback_query(cb_id)
            return True

        # B) Admin callbacks (tgadm:*)
        if payload.startswith("tgadm:"):
            if not is_admin:
                if cb_id:
                    await bot.answer_callback_query(cb_id, text="⛔ Нема доступу", show_alert=False)
                return True
            handled = await admin_handle_update(tenant=tenant, data=data, bot=bot)
            if cb_id:
                await bot.answer_callback_query(cb_id)
            return bool(handled)

        # C) Cart callbacks
        if payload.startswith("tgcart:"):
            handled = await handle_cart_callback(
                bot=bot,
                tenant_id=tenant_id,
                user_id=user_id,
                chat_id=chat_id,
                message_id=msg_id,
                payload=payload,
            )
            if cb_id:
                await bot.answer_callback_query(cb_id)
            return bool(handled)

        # D) Favorites callbacks (tgfav:*)
        if payload.startswith("tgfav:"):
            handled = await handle_favorites_callback(
                bot=bot,
                tenant_id=tenant_id,
                user_id=user_id,
                chat_id=chat_id,
                message_id=msg_id,
                payload=payload,
            )
            if cb_id:
                await bot.answer_callback_query(cb_id)
            return bool(handled)

        # E) Orders callbacks (tgord:*)
        if payload.startswith("tgord:"):
            handled = await handle_orders_callback(
                bot=bot,
                tenant_id=tenant_id,
                user_id=user_id,
                chat_id=chat_id,
                payload=payload,
                message_id=msg_id,
            )
            if cb_id:
                await bot.answer_callback_query(cb_id)
            return bool(handled)

        # F) Shop callbacks
        if not payload.startswith("tgshop:"):
            return False

        parts = payload.split(":")
        action = parts[1] if len(parts) > 1 else ""
        pid = int(parts[2]) if len(parts) > 2 and str(parts[2]).isdigit() else 0
        cid_raw = parts[3] if len(parts) > 3 else "0"
        cid = int(cid_raw) if str(cid_raw).isdigit() else 0
        category_id = cid if cid > 0 else None
        scope = (parts[4] if len(parts) > 4 else "").strip() or "cat"

        if action == "noop":
            if cb_id:
                await bot.answer_callback_query(cb_id, text="•", show_alert=False)
            return True

        if action == "hp":
            await _send_hits_promos_entry(bot, chat_id, is_admin=is_admin)
            if cb_id:
                await bot.answer_callback_query(cb_id)
            return True

        if action == "pcats":
            await _send_scope_categories(bot, chat_id, tenant_id, scope="promo")
            if cb_id:
                await bot.answer_callback_query(cb_id)
            return True

        if action == "hcats":
            await _send_scope_categories(bot, chat_id, tenant_id, scope="hit")
            if cb_id:
                await bot.answer_callback_query(cb_id)
            return True

        if action == "pcat":
            await _send_first_product_card(bot, chat_id, tenant_id, user_id, is_admin=is_admin, category_id=category_id, scope="promo")
            if cb_id:
                await bot.answer_callback_query(cb_id)
            return True

        if action == "hcat":
            await _send_first_product_card(bot, chat_id, tenant_id, user_id, is_admin=is_admin, category_id=category_id, scope="hit")
            if cb_id:
                await bot.answer_callback_query(cb_id)
            return True

        if action == "cat":
            await _send_first_product_card(bot, chat_id, tenant_id, user_id, is_admin=is_admin, category_id=category_id, scope="cat")
            if cb_id:
                await bot.answer_callback_query(cb_id)
            return True

        if action == "add" and pid > 0:
            await TelegramShopCartRepo.cart_inc(tenant_id, user_id, pid, 1)
            if cb_id:
                await bot.answer_callback_query(cb_id, text="✅ Додано в кошик", show_alert=False)
            return True

        if action == "fav" and pid > 0:
            added = await TelegramShopFavoritesRepo.toggle(tenant_id, user_id, pid)
            try:
                await _edit_product_kb_only(
                    bot,
                    chat_id,
                    msg_id,
                    tenant_id,
                    user_id,
                    pid,
                    category_id=category_id,
                    scope=scope,
                )
            except Exception:
                pass

            if cb_id:
                await bot.answer_callback_query(
                    cb_id,
                    text="⭐ Додано в обране" if added else "⭐ Прибрано з обраного",
                    show_alert=False,
                )
            return True

        if action in ("prev", "next", "pprev", "pnext", "hprev", "hnext") and pid > 0:
            if action == "prev":
                p = await ProductsRepo.get_prev_active(tenant_id, pid, category_id=category_id)
                sc = "cat"
            elif action == "next":
                p = await ProductsRepo.get_next_active(tenant_id, pid, category_id=category_id)
                sc = "cat"
            elif action == "pprev":
                p = await ProductsRepo.get_prev_promo_active(tenant_id, pid, category_id=category_id)
                sc = "promo"
            elif action == "pnext":
                p = await ProductsRepo.get_next_promo_active(tenant_id, pid, category_id=category_id)
                sc = "promo"
            elif action == "hprev":
                p = await ProductsRepo.get_prev_hit_active(tenant_id, pid, category_id=category_id)
                sc = "hit"
            else:
                p = await ProductsRepo.get_next_hit_active(tenant_id, pid, category_id=category_id)
                sc = "hit"

            if not p:
                if cb_id:
                    await bot.answer_callback_query(cb_id, text="•", show_alert=False)
                return True

            await _edit_product_card(bot, chat_id, msg_id, tenant_id, user_id, int(p["id"]), category_id=category_id, scope=sc)
            if cb_id:
                await bot.answer_callback_query(cb_id)
            return True

        if cb_id:
            await bot.answer_callback_query(cb_id)
        return False

    # --- messages ---
    msg = _extract_message(data)
    if not msg:
        return False

    chat_id = int(msg["chat"]["id"])
    user_id = int(msg["from"]["id"])
    is_admin = is_admin_user(tenant=tenant, user_id=user_id)

    text = _get_text(msg)
    if not text:
        return False

    text_l = text.lower()
    log.info("tgshop message text=%r user_id=%s tenant=%s", text, user_id, tenant_id)

    # ✅ 0) адмінські "wizard/state" перехоплюємо ПЕРШИМ
    # (це і є фікс: додавання товару, автопост chat_id/url, тощо)
    if is_admin and text_l not in ("/start", "/shop", "/sup", "/support_admin"):
        try:
            handled = await admin_handle_update(tenant=tenant, data=data, bot=bot)
            if handled:
                return True
        except Exception:
            pass

    # A) pending support edit (admin)
    pend = _PENDING_SUPPORT_EDIT.get((tenant_id, user_id))
    if is_admin and pend:
        if text_l == "/cancel":
            _PENDING_SUPPORT_EDIT.pop((tenant_id, user_id), None)
            await bot.send_message(chat_id, "❌ Скасовано.", reply_markup=main_menu_kb(is_admin=True))
            return True

        key = str(pend["key"])
        await TelegramShopSupportLinksRepo.set_url(tenant_id, key, text.strip())
        _PENDING_SUPPORT_EDIT.pop((tenant_id, user_id), None)
        await bot.send_message(chat_id, "✅ Оновив значення. /sup щоб глянути меню ще раз.")
        return True

    # B) Admin quick
    if is_admin and (text == _normalize_text(BTN_ADMIN) or text_l == "/a" or text_l == "/a_help"):
        handled = await admin_handle_update(tenant=tenant, data=data, bot=bot)
        return bool(handled)

    # C) Support admin menu
    if is_admin and text_l in ("/sup", "/support_admin"):
        await _send_support_admin(bot, chat_id, tenant_id)
        return True

    if text_l in ("/start", "/shop"):
        await _send_menu(bot, chat_id, "🛒 *Магазин*\n\nОбирай розділ кнопками нижче 👇", is_admin=is_admin)
        return True

    if text == _normalize_text(BTN_CATALOG):
        await _send_categories_menu(bot, chat_id, tenant_id, is_admin=is_admin)
        return True

    if text == _normalize_text(BTN_CART):
        await send_cart(bot, chat_id, tenant_id, user_id)
        return True

    # Cart actions
    if text in (_normalize_text(BTN_CLEAR_CART), _normalize_text(BTN_CHECKOUT)):
        handled = await handle_cart_message(
            bot=bot,
            tenant_id=tenant_id,
            user_id=user_id,
            chat_id=chat_id,
            text=text,
        )
        return bool(handled)

    # Admin Orders button
    if is_admin and (text == _normalize_text(BTN_ADMIN_ORDERS) or text_l.strip() == "замовлення"):
        await admin_orders_send_menu(bot, chat_id)
        return True

    # Orders history (user)
    if text == _normalize_text(BTN_ORDERS) or (("істор" in text_l) and ("замов" in text_l)):
        await send_orders_list(bot, chat_id, tenant_id, user_id)
        return True

    if text == _normalize_text(BTN_HITS):
        await _send_hits_promos_entry(bot, chat_id, is_admin=is_admin)
        return True

    if text == _normalize_text(BTN_FAV):
        await send_favorites(bot, chat_id, tenant_id, user_id, is_admin=is_admin)
        return True

    if text == _normalize_text(BTN_SUPPORT):
        await send_support_menu(bot, chat_id, tenant_id, is_admin=is_admin)
        return True

    if text == _normalize_text(BTN_MENU_BACK):
        await _send_menu(bot, chat_id, "⬅️ Повернув у меню 👇", is_admin=is_admin)
        return True

    return False