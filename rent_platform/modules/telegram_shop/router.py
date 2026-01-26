# -*- coding: utf-8 -*-
from __future__ import annotations

import time
import logging
from typing import Any

from aiogram import Bot
from aiogram.types import InputMediaPhoto

from rent_platform.modules.telegram_shop.admin import admin_handle_update, is_admin_user
from rent_platform.modules.telegram_shop.repo.products import ProductsRepo
from rent_platform.modules.telegram_shop.repo.cart import TelegramShopCartRepo
from rent_platform.modules.telegram_shop.repo.orders import TelegramShopOrdersRepo
from rent_platform.modules.telegram_shop.ui.user_kb import (
    main_menu_kb,
    catalog_kb,
    cart_kb,
    favorites_kb,
    orders_history_kb,
    support_kb,
    BTN_CATALOG,
    BTN_CART,
    BTN_HITS,
    BTN_FAV,
    BTN_ORDERS,
    BTN_SUPPORT,
    BTN_MENU_BACK,
    BTN_ADMIN,
    BTN_CHECKOUT,
    BTN_CLEAR_CART,
)
from rent_platform.modules.telegram_shop.ui.inline_kb import (
    product_card_kb,
    catalog_categories_kb,
)
from rent_platform.modules.telegram_shop.user_cart import (
    send_cart,
    handle_cart_message,
    handle_cart_callback,
)

try:
    from rent_platform.modules.telegram_shop.repo.categories import CategoriesRepo  # type: ignore
except Exception:  # pragma: no cover
    CategoriesRepo = None  # type: ignore

log = logging.getLogger(__name__)


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


def _scope_product_kb(scope: str, *, product_id: int, has_prev: bool, has_next: bool, category_id: int | None) -> dict:
    """
    scope:
      "cat"   - звичайний каталог (використовуємо product_card_kb з inline_kb)
      "promo" - акції
      "hit"   - хіти
    """
    cid = int(category_id or 0)

    if scope == "cat":
        return product_card_kb(
            product_id=product_id,
            has_prev=has_prev,
            has_next=has_next,
            category_id=category_id,
        )

    # scoped prev/next — щоб не стрибало в звичайний каталог
    prev_action = "pprev" if scope == "promo" else "hprev"
    next_action = "pnext" if scope == "promo" else "hnext"
    cats_action = "pcats" if scope == "promo" else "hcats"

    nav_row: list[tuple[str, str]] = [
        ("⬅️", f"tgshop:{prev_action}:{product_id}:{cid}") if has_prev else ("·", "tgshop:noop:0:0"),
        ("➡️", f"tgshop:{next_action}:{product_id}:{cid}") if has_next else ("·", "tgshop:noop:0:0"),
    ]

    return _kb([
        nav_row,
        [("🛒 Додати", f"tgshop:add:{product_id}:{cid}"), ("⭐", f"tgshop:fav:{product_id}:{cid}")],
        [("📁 Категорії", f"tgshop:{cats_action}:0:0")],
    ])


async def _send_menu(bot: Bot, chat_id: int, text: str, *, is_admin: bool) -> None:
    await bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=main_menu_kb(is_admin=is_admin))


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
# Hits / Promos menus (categories filtered)
# =========================================================
async def _send_hits_promos_entry(bot: Bot, chat_id: int, *, is_admin: bool) -> None:
    kb = _kb([
        [("🔥 Акції", "tgshop:pcats:0:0"), ("⭐ Хіти", "tgshop:hcats:0:0")],
    ])
    await bot.send_message(
        chat_id,
        "🔥 *Хіти / Акції*\n\n"
        "Обери режим 👇\n\n"
        "• *Акції* — товари з активною знижкою 🔥\n"
        "• *Хіти* — добірка найкращих товарів ✨\n",
        parse_mode="Markdown",
        reply_markup=kb,
    )


async def _send_scope_categories(bot: Bot, chat_id: int, tenant_id: str, *, scope: str) -> None:
    """
    scope: "promo" | "hit"
    показує лише ті категорії, де є контент
    """
    if CategoriesRepo is None:
        await bot.send_message(
            chat_id,
            "🔥 *Хіти / Акції*\n\nКатегорії ще не підключені.",
            parse_mode="Markdown",
        )
        return

    await CategoriesRepo.ensure_default(tenant_id)  # type: ignore[misc]

    # беремо public категорії і фільтруємо по ids, які реально мають контент
    cats_all = await CategoriesRepo.list_public(tenant_id, limit=100)  # type: ignore[misc]
    ids_set: set[int]

    if scope == "promo":
        ids = await ProductsRepo.list_promo_category_ids(tenant_id)
        ids_set = set(ids)
        title = "🔥 *Акції*"
        empty_txt = "Немає акційних товарів 😅"
        action = "pcat"
    else:
        ids = await ProductsRepo.list_hit_category_ids(tenant_id)
        ids_set = set(ids)
        title = "⭐ *Хіти*"
        empty_txt = "Немає хітів 😅"
        action = "hcat"

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
        rows.append([(f"📁 {name}", f"tgshop:{action}:0:{cid}")])

    # назад до вибору режиму
    rows.append([("⬅️ Назад", "tgshop:hp:0:0")])

    await bot.send_message(
        chat_id,
        f"{title}\n\nОбери категорію 👇",
        parse_mode="Markdown",
        reply_markup=_kb(rows),
    )


# =========================================================
# Product card rendering (catalog / promo / hit)
# =========================================================
async def _build_product_card(
    tenant_id: str,
    product_id: int,
    *,
    category_id: int | None,
    scope: str,  # "cat" | "promo" | "hit"
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

    # prev/next залежить від scope
    if scope == "cat":
        prev_p = await ProductsRepo.get_prev_active(tenant_id, pid, category_id=category_id)
        next_p = await ProductsRepo.get_next_active(tenant_id, pid, category_id=category_id)
    elif scope == "promo":
        prev_p = await ProductsRepo.get_prev_promo_active(tenant_id, pid, category_id=category_id)
        next_p = await ProductsRepo.get_next_promo_active(tenant_id, pid, category_id=category_id)
    else:  # hit
        prev_p = await ProductsRepo.get_prev_hit_active(tenant_id, pid, category_id=category_id)
        next_p = await ProductsRepo.get_next_hit_active(tenant_id, pid, category_id=category_id)

    cover_file_id = await ProductsRepo.get_cover_photo_file_id(tenant_id, pid)

    # Заголовок з бейджем режиму
    badge = ""
    if scope == "promo":
        badge = "🔥 "
    elif scope == "hit":
        badge = "⭐ "

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

    kb = _scope_product_kb(
        scope=scope,
        product_id=pid,
        has_prev=bool(prev_p),
        has_next=bool(next_p),
        category_id=category_id,
    )

    return {
        "pid": pid,
        "has_photo": bool(cover_file_id),
        "file_id": cover_file_id,
        "text": text,
        "kb": kb,
    }


async def _send_first_product_card(
    bot: Bot,
    chat_id: int,
    tenant_id: str,
    *,
    is_admin: bool,
    category_id: int | None,
    scope: str,  # "cat" | "promo" | "hit"
) -> None:
    # беремо перший товар залежно від режиму
    if scope == "cat":
        first = await ProductsRepo.get_first_active(tenant_id, category_id=category_id)
    elif scope == "promo":
        first = await ProductsRepo.get_first_promo_active(tenant_id, category_id=category_id)
    else:
        first = await ProductsRepo.get_first_hit_active(tenant_id, category_id=category_id)

    if not first:
        if scope == "cat":
            await bot.send_message(
                chat_id,
                "🛍 *Каталог*\n\nПоки що немає товарів у цій категорії.",
                parse_mode="Markdown",
            )
            await _send_categories_menu(bot, chat_id, tenant_id, is_admin=is_admin)
        elif scope == "promo":
            await bot.send_message(chat_id, "🔥 *Акції*\n\nУ цій категорії немає акційних товарів.", parse_mode="Markdown")
            await _send_scope_categories(bot, chat_id, tenant_id, scope="promo")
        else:
            await bot.send_message(chat_id, "⭐ *Хіти*\n\nУ цій категорії немає хітів.", parse_mode="Markdown")
            await _send_scope_categories(bot, chat_id, tenant_id, scope="hit")
        return

    card = await _build_product_card(tenant_id, int(first["id"]), category_id=category_id, scope=scope)
    if not card:
        await bot.send_message(chat_id, "Поки що порожньо 😅", parse_mode="Markdown")
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


async def _edit_product_card(
    bot: Bot,
    chat_id: int,
    message_id: int,
    tenant_id: str,
    product_id: int,
    *,
    category_id: int | None,
    scope: str,  # "cat" | "promo" | "hit"
) -> bool:
    card = await _build_product_card(tenant_id, product_id, category_id=category_id, scope=scope)
    if not card:
        return False

    if card["has_photo"]:
        media = InputMediaPhoto(media=card["file_id"], caption=card["text"], parse_mode="Markdown")
        await bot.edit_message_media(
            media=media,
            chat_id=chat_id,
            message_id=message_id,
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


# =========================================================
# Orders
# =========================================================
async def _send_orders(bot: Bot, chat_id: int, tenant_id: str, user_id: int, *, is_admin: bool) -> None:
    orders = await TelegramShopOrdersRepo.list_orders(tenant_id, user_id, limit=20)
    if not orders:
        await bot.send_message(
            chat_id,
            "🧾 *Історія замовлень*\n\nПоки що порожньо.",
            parse_mode="Markdown",
            reply_markup=orders_history_kb(is_admin=is_admin),
        )
        return

    lines = ["🧾 *Історія замовлень*\n"]
    for o in orders:
        oid = int(o["id"])
        status = str(o["status"])
        total = int(o["total_kop"] or 0)
        lines.append(f"#{oid} — *{status}* — {_fmt_money(total)}")

    await bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown", reply_markup=orders_history_kb(is_admin=is_admin))


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

        # 1) Admin callbacks first
        if payload.startswith("tgadm:"):
            if not is_admin:
                if cb_id:
                    await bot.answer_callback_query(cb_id, text="⛔ Нема доступу", show_alert=False)
                return True
            handled = await admin_handle_update(tenant=tenant, data=data, bot=bot)
            return bool(handled)

        # 2) Cart callbacks
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

        # 3) Shop callbacks
        if not payload.startswith("tgshop:"):
            return False

        parts = payload.split(":")
        action = parts[1] if len(parts) > 1 else ""
        pid = int(parts[2]) if len(parts) > 2 and str(parts[2]).isdigit() else 0
        cid_raw = parts[3] if len(parts) > 3 else "0"
        cid = int(cid_raw) if str(cid_raw).isdigit() else 0
        category_id = cid if cid > 0 else None

        # common noop
        if action == "noop":
            if cb_id:
                await bot.answer_callback_query(cb_id, text="•", show_alert=False)
            return True

        # ---- Hits/Promos entry + categories
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
            await _send_first_product_card(bot, chat_id, tenant_id, is_admin=is_admin, category_id=category_id, scope="promo")
            if cb_id:
                await bot.answer_callback_query(cb_id)
            return True

        if action == "hcat":
            await _send_first_product_card(bot, chat_id, tenant_id, is_admin=is_admin, category_id=category_id, scope="hit")
            if cb_id:
                await bot.answer_callback_query(cb_id)
            return True

        # ---- Catalog category open
        if action == "cat":
            await _send_first_product_card(bot, chat_id, tenant_id, is_admin=is_admin, category_id=category_id, scope="cat")
            if cb_id:
                await bot.answer_callback_query(cb_id)
            return True

        # ---- Add/fav (same for all scopes)
        if action == "add" and pid > 0:
            await TelegramShopCartRepo.cart_inc(tenant_id, user_id, pid, 1)
            if cb_id:
                await bot.answer_callback_query(cb_id, text="✅ Додано в кошик", show_alert=False)
            return True

        if action == "fav" and pid > 0:
            if cb_id:
                await bot.answer_callback_query(cb_id, text="⭐ Додано в обране (скоро буде логіка)", show_alert=False)
            return True

        # ---- Catalog prev/next
        if action == "prev" and pid > 0:
            p = await ProductsRepo.get_prev_active(tenant_id, pid, category_id=category_id)
            if not p:
                if cb_id:
                    await bot.answer_callback_query(cb_id, text="•", show_alert=False)
                return True
            await _edit_product_card(bot, chat_id, msg_id, tenant_id, int(p["id"]), category_id=category_id, scope="cat")
            if cb_id:
                await bot.answer_callback_query(cb_id)
            return True

        if action == "next" and pid > 0:
            p = await ProductsRepo.get_next_active(tenant_id, pid, category_id=category_id)
            if not p:
                if cb_id:
                    await bot.answer_callback_query(cb_id, text="•", show_alert=False)
                return True
            await _edit_product_card(bot, chat_id, msg_id, tenant_id, int(p["id"]), category_id=category_id, scope="cat")
            if cb_id:
                await bot.answer_callback_query(cb_id)
            return True

        # ---- Promo prev/next
        if action == "pprev" and pid > 0:
            p = await ProductsRepo.get_prev_promo_active(tenant_id, pid, category_id=category_id)
            if not p:
                if cb_id:
                    await bot.answer_callback_query(cb_id, text="•", show_alert=False)
                return True
            await _edit_product_card(bot, chat_id, msg_id, tenant_id, int(p["id"]), category_id=category_id, scope="promo")
            if cb_id:
                await bot.answer_callback_query(cb_id)
            return True

        if action == "pnext" and pid > 0:
            p = await ProductsRepo.get_next_promo_active(tenant_id, pid, category_id=category_id)
            if not p:
                if cb_id:
                    await bot.answer_callback_query(cb_id, text="•", show_alert=False)
                return True
            await _edit_product_card(bot, chat_id, msg_id, tenant_id, int(p["id"]), category_id=category_id, scope="promo")
            if cb_id:
                await bot.answer_callback_query(cb_id)
            return True

        # ---- Hit prev/next
        if action == "hprev" and pid > 0:
            p = await ProductsRepo.get_prev_hit_active(tenant_id, pid, category_id=category_id)
            if not p:
                if cb_id:
                    await bot.answer_callback_query(cb_id, text="•", show_alert=False)
                return True
            await _edit_product_card(bot, chat_id, msg_id, tenant_id, int(p["id"]), category_id=category_id, scope="hit")
            if cb_id:
                await bot.answer_callback_query(cb_id)
            return True

        if action == "hnext" and pid > 0:
            p = await ProductsRepo.get_next_hit_active(tenant_id, pid, category_id=category_id)
            if not p:
                if cb_id:
                    await bot.answer_callback_query(cb_id, text="•", show_alert=False)
                return True
            await _edit_product_card(bot, chat_id, msg_id, tenant_id, int(p["id"]), category_id=category_id, scope="hit")
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

    # Admin handler FIRST
    if is_admin:
        handled = await admin_handle_update(tenant=tenant, data=data, bot=bot)
        if handled:
            return True

    text = _get_text(msg)
    if not text:
        return False

    log.info("tgshop message text=%r user_id=%s tenant=%s", text, user_id, tenant_id)

    if text in ("/start", "/shop"):
        await _send_menu(bot, chat_id, "🛒 *Магазин*\n\nОбирай розділ кнопками нижче 👇", is_admin=is_admin)
        return True

    if text == _normalize_text(BTN_CATALOG):
        await _send_categories_menu(bot, chat_id, tenant_id, is_admin=is_admin)
        return True

    if text == _normalize_text(BTN_CART):
        await send_cart(bot, chat_id, tenant_id, user_id)
        return True

    # Cart actions via reply keyboard
    if text in (_normalize_text(BTN_CLEAR_CART), _normalize_text(BTN_CHECKOUT)):
        handled = await handle_cart_message(
            bot=bot,
            tenant_id=tenant_id,
            user_id=user_id,
            chat_id=chat_id,
            text=text,
        )
        return bool(handled)

    if text == _normalize_text(BTN_ORDERS):
        await _send_orders(bot, chat_id, tenant_id, user_id, is_admin=is_admin)
        return True

    if text == _normalize_text(BTN_HITS):
        await _send_hits_promos_entry(bot, chat_id, is_admin=is_admin)
        return True

    if text == _normalize_text(BTN_FAV):
        await bot.send_message(
            chat_id,
            "⭐ *Обране*\n\nПоки що в розробці (гачок готовий).",
            parse_mode="Markdown",
            reply_markup=favorites_kb(is_admin=is_admin),
        )
        return True

    if text == _normalize_text(BTN_SUPPORT):
        await bot.send_message(
            chat_id,
            "🆘 *Підтримка*\n\nПоки що в розробці (гачок готовий).",
            parse_mode="Markdown",
            reply_markup=support_kb(is_admin=is_admin),
        )
        return True

    if text == _normalize_text(BTN_MENU_BACK):
        await _send_menu(bot, chat_id, "⬅️ Повернув у меню 👇", is_admin=is_admin)
        return True

    if text == _normalize_text(BTN_ADMIN) and is_admin:
        await bot.send_message(chat_id, "🛠 Адмінка: /a_help", reply_markup=main_menu_kb(is_admin=True))
        return True

    return False