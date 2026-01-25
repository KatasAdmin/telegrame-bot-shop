# -*- coding: utf-8 -*-
from __future__ import annotations

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
    cart_inline,
    catalog_categories_kb,
)

try:
    from rent_platform.modules.telegram_shop.repo.categories import CategoriesRepo  # type: ignore
except Exception:  # pragma: no cover
    CategoriesRepo = None  # type: ignore

log = logging.getLogger(__name__)


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


async def _send_menu(bot: Bot, chat_id: int, text: str, *, is_admin: bool) -> None:
    await bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=main_menu_kb(is_admin=is_admin))


# ---------- Catalog categories ----------

async def _send_categories_menu(bot: Bot, chat_id: int, tenant_id: str, *, is_admin: bool) -> None:
    """
    Показує юзеру КАТЕГОРІЇ як inline-кнопки.
    ВАЖЛИВО:
      - беремо тільки публічні (sort >= 0, без __...__)
      - кнопку "🌐 Усі товари" показуємо тільки якщо адмін увімкнув
      - "Без категорії" показується лише якщо адмін зробив її видимою
    """
    if CategoriesRepo is None:
        await bot.send_message(
            chat_id,
            "🛍 *Каталог*\n\nКатегорії ще не підключені.",
            parse_mode="Markdown",
            reply_markup=catalog_kb(is_admin=is_admin),
        )
        return

    # гарантуємо, що дефолт/флаг існують
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


# ---------- Product card rendering ----------

async def _build_product_card(tenant_id: str, product_id: int, *, category_id: int | None) -> dict | None:
    p = await ProductsRepo.get_active(tenant_id, product_id)
    if not p:
        return None

    pid = int(p["id"])
    name = str(p["name"])
    price = int(p.get("price_kop") or 0)
    desc = (p.get("description") or "").strip()

    prev_p = await ProductsRepo.get_prev_active(tenant_id, pid, category_id=category_id)
    next_p = await ProductsRepo.get_next_active(tenant_id, pid, category_id=category_id)

    cover_file_id = await ProductsRepo.get_cover_photo_file_id(tenant_id, pid)

    text = (
        f"🛍 *{name}*\n\n"
        f"Ціна: *{_fmt_money(price)}*\n"
        f"ID: `{pid}`"
    )
    if desc:
        text += f"\n\n{desc}"

    kb = product_card_kb(
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
) -> None:
    p = await ProductsRepo.get_first_active(tenant_id, category_id=category_id)
    if not p:
        await bot.send_message(
            chat_id,
            "🛍 *Каталог*\n\nПоки що немає товарів у цій категорії.",
            parse_mode="Markdown",
        )
        await _send_categories_menu(bot, chat_id, tenant_id, is_admin=is_admin)
        return

    card = await _build_product_card(tenant_id, int(p["id"]), category_id=category_id)
    if not card:
        await bot.send_message(chat_id, "🛍 Каталог поки що порожній.")
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
) -> bool:
    card = await _build_product_card(tenant_id, product_id, category_id=category_id)
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


# ---------- Cart rendering ----------

async def _render_cart_text(tenant_id: str, user_id: int) -> tuple[str, list[dict]]:
    items = await TelegramShopCartRepo.cart_list(tenant_id, user_id)
    if not items:
        return ("🛒 *Кошик*\n\nПорожньо.", [])

    total = 0
    lines = ["🛒 *Кошик*\n"]
    for it in items:
        name = str(it["name"])
        qty = int(it["qty"])
        price = int(it.get("price_kop") or 0)
        total += price * qty
        lines.append(f"{name}\n{qty} × {_fmt_money(price)} = *{_fmt_money(price * qty)}*")
    lines.append(f"\nРазом: *{_fmt_money(total)}*")
    return ("\n\n".join(lines), items)


async def _send_cart(bot: Bot, chat_id: int, tenant_id: str, user_id: int, *, is_admin: bool) -> None:
    text, items = await _render_cart_text(tenant_id, user_id)
    await bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=cart_kb(is_admin=is_admin))
    if items:
        await bot.send_message(chat_id, "⚙️ Керування кошиком:", reply_markup=cart_inline(items=items))


async def _edit_cart_inline(bot: Bot, chat_id: int, message_id: int, tenant_id: str, user_id: int) -> None:
    text, items = await _render_cart_text(tenant_id, user_id)
    if not items:
        await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode="Markdown")
        return
    await bot.edit_message_text(
        text,
        chat_id=chat_id,
        message_id=message_id,
        parse_mode="Markdown",
        reply_markup=cart_inline(items=items),
    )


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


# ---------- Main entry ----------

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

        # 1) Admin callbacks first
        if payload.startswith("tgadm:"):
            if not is_admin:
                if cb_id:
                    await bot.answer_callback_query(cb_id, text="⛔ Нема доступу", show_alert=False)
                return True
            handled = await admin_handle_update(tenant=tenant, data=data, bot=bot)
            return bool(handled)

        # 2) Shop callbacks
        if not payload.startswith("tgshop:"):
            return False

        msg_id = int(cb["message"]["message_id"])

        parts = payload.split(":")
        action = parts[1] if len(parts) > 1 else ""
        pid = int(parts[2]) if len(parts) > 2 and str(parts[2]).isdigit() else 0

        cid_raw = parts[3] if len(parts) > 3 else "0"
        cid = int(cid_raw) if str(cid_raw).isdigit() else 0
        category_id = cid if cid > 0 else None

        if action == "noop":
            if cb_id:
                await bot.answer_callback_query(cb_id, text="•", show_alert=False)
            return True

        if action == "cats":
            await _send_categories_menu(bot, chat_id, tenant_id, is_admin=is_admin)
            if cb_id:
                await bot.answer_callback_query(cb_id)
            return True

        # open category (cid) or 0 = all
        if action == "cat":
            await _send_first_product_card(bot, chat_id, tenant_id, is_admin=is_admin, category_id=category_id)
            if cb_id:
                await bot.answer_callback_query(cb_id)
            return True

        if action == "add" and pid > 0:
            await TelegramShopCartRepo.cart_inc(tenant_id, user_id, pid, 1)
            if cb_id:
                await bot.answer_callback_query(cb_id, text="✅ Додано в кошик", show_alert=False)
            return True

        if action == "fav" and pid > 0:
            if cb_id:
                await bot.answer_callback_query(cb_id, text="⭐ Додано в обране (скоро буде логіка)", show_alert=False)
            return True

        if action == "prev" and pid > 0:
            p = await ProductsRepo.get_prev_active(tenant_id, pid, category_id=category_id)
            if not p:
                if cb_id:
                    await bot.answer_callback_query(cb_id, text="•", show_alert=False)
                return True
            await _edit_product_card(bot, chat_id, msg_id, tenant_id, int(p["id"]), category_id=category_id)
            if cb_id:
                await bot.answer_callback_query(cb_id)
            return True

        if action == "next" and pid > 0:
            p = await ProductsRepo.get_next_active(tenant_id, pid, category_id=category_id)
            if not p:
                if cb_id:
                    await bot.answer_callback_query(cb_id, text="•", show_alert=False)
                return True
            await _edit_product_card(bot, chat_id, msg_id, tenant_id, int(p["id"]), category_id=category_id)
            if cb_id:
                await bot.answer_callback_query(cb_id)
            return True

        if action == "inc" and pid > 0:
            await TelegramShopCartRepo.cart_inc(tenant_id, user_id, pid, 1)
            await _edit_cart_inline(bot, chat_id, msg_id, tenant_id, user_id)
            if cb_id:
                await bot.answer_callback_query(cb_id)
            return True

        if action == "dec" and pid > 0:
            await TelegramShopCartRepo.cart_inc(tenant_id, user_id, pid, -1)
            await _edit_cart_inline(bot, chat_id, msg_id, tenant_id, user_id)
            if cb_id:
                await bot.answer_callback_query(cb_id)
            return True

        if action == "del" and pid > 0:
            await TelegramShopCartRepo.cart_delete_item(tenant_id, user_id, pid)
            await _edit_cart_inline(bot, chat_id, msg_id, tenant_id, user_id)
            if cb_id:
                await bot.answer_callback_query(cb_id)
            return True

        if action == "clear":
            await TelegramShopCartRepo.cart_clear(tenant_id, user_id)
            await _edit_cart_inline(bot, chat_id, msg_id, tenant_id, user_id)
            if cb_id:
                await bot.answer_callback_query(cb_id)
            return True

        if action == "checkout":
            oid = await TelegramShopOrdersRepo.create_order_from_cart(tenant_id, user_id)
            if not oid:
                await bot.send_message(
                    chat_id,
                    "🛒 Кошик порожній — нічого оформлювати.",
                    reply_markup=cart_kb(is_admin=is_admin),
                )
            else:
                await bot.send_message(
                    chat_id,
                    f"✅ Замовлення *#{oid}* створено!",
                    parse_mode="Markdown",
                    reply_markup=main_menu_kb(is_admin=is_admin),
                )
            await _edit_cart_inline(bot, chat_id, msg_id, tenant_id, user_id)
            if cb_id:
                await bot.answer_callback_query(cb_id)
            return True

        if cb_id:
            await bot.answer_callback_query(cb_id)
        return False

    # --- messages (IMPORTANT: admin must see photo messages too) ---
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
        await _send_cart(bot, chat_id, tenant_id, user_id, is_admin=is_admin)
        return True

    if text == _normalize_text(BTN_ORDERS):
        await _send_orders(bot, chat_id, tenant_id, user_id, is_admin=is_admin)
        return True

    if text == _normalize_text(BTN_HITS):
        await bot.send_message(
            chat_id,
            "🔥 *Хіти / Акції*\n\nПоки що в розробці (гачок готовий).",
            parse_mode="Markdown",
            reply_markup=catalog_kb(is_admin=is_admin),
        )
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

    if text == _normalize_text(BTN_CLEAR_CART):
        await TelegramShopCartRepo.cart_clear(tenant_id, user_id)
        await _send_cart(bot, chat_id, tenant_id, user_id, is_admin=is_admin)
        return True

    if text == _normalize_text(BTN_CHECKOUT):
        oid = await TelegramShopOrdersRepo.create_order_from_cart(tenant_id, user_id)
        if not oid:
            await bot.send_message(
                chat_id,
                "🛒 Кошик порожній — нічого оформлювати.",
                reply_markup=cart_kb(is_admin=is_admin),
            )
        else:
            await bot.send_message(
                chat_id,
                f"✅ Замовлення *#{oid}* створено!",
                parse_mode="Markdown",
                reply_markup=main_menu_kb(is_admin=is_admin),
            )
        return True

    if text == _normalize_text(BTN_ADMIN) and is_admin:
        await bot.send_message(chat_id, "🛠 Адмінка: /a_help", reply_markup=main_menu_kb(is_admin=True))
        return True

    return False