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
from rent_platform.modules.telegram_shop.ui.inline_kb import product_card_kb, cart_inline

log = logging.getLogger(__name__)


def _extract_message(update: dict) -> dict | None:
    return update.get("message") or update.get("edited_message")


def _extract_callback(update: dict) -> dict | None:
    return update.get("callback_query")


def _normalize_text(s: str) -> str:
    """
    Telegram/iOS can send emoji texts with variation selectors.
    We normalize so comparisons with BTN_* are stable.
    """
    s = (s or "").strip()
    # remove common emoji variation selectors / joiners
    s = s.replace("\ufe0f", "").replace("\u200d", "")
    # collapse whitespace
    s = " ".join(s.split())
    return s


def _get_text(msg: dict) -> str:
    return _normalize_text((msg.get("text") or ""))


def _fmt_money(kop: int) -> str:
    kop = int(kop or 0)
    Ð³ÑÐ½ = kop // 100
    ÐºÐ¾Ð¿ = kop % 100
    return f"{Ð³ÑÐ½}.{ÐºÐ¾Ð¿:02d} Ð³ÑÐ½"


async def _send_menu(bot: Bot, chat_id: int, text: str, *, is_admin: bool) -> None:
    await bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=main_menu_kb(is_admin=is_admin))


# ---------- Catalog / product card rendering ----------

async def _build_product_card(tenant_id: str, product_id: int) -> dict | None:
    p = await ProductsRepo.get_active(tenant_id, product_id)
    if not p:
        return None

    prev_p = await ProductsRepo.get_prev_active(tenant_id, product_id)
    next_p = await ProductsRepo.get_next_active(tenant_id, product_id)

    pid = int(p["id"])
    name = str(p["name"])
    price = int(p.get("price_kop") or 0)
    desc = (p.get("description") or "").strip()

    cover_file_id = await ProductsRepo.get_cover_photo_file_id(tenant_id, pid)

    text = (
        f"ð *{name}*\n\n"
        f"Ð¦ÑÐ½Ð°: *{_fmt_money(price)}*\n"
        f"ID: `{pid}`"
    )
    if desc:
        text += f"\n\n{desc}"

    kb = product_card_kb(product_id=pid, has_prev=bool(prev_p), has_next=bool(next_p))

    return {
        "pid": pid,
        "has_photo": bool(cover_file_id),
        "file_id": cover_file_id,
        "text": text,
        "kb": kb,
    }


async def _send_first_product_card(bot: Bot, chat_id: int, tenant_id: str, *, is_admin: bool) -> None:
    p = await ProductsRepo.get_first_active(tenant_id)
    if not p:
        await bot.send_message(
            chat_id,
            "ð *ÐÐ°ÑÐ°Ð»Ð¾Ð³*\n\nÐÐ¾ÐºÐ¸ ÑÐ¾ Ð½ÐµÐ¼Ð°Ñ ÑÐ¾Ð²Ð°ÑÑÐ².",
            parse_mode="Markdown",
            reply_markup=catalog_kb(is_admin=is_admin),
        )
        return

    card = await _build_product_card(tenant_id, int(p["id"]))
    if not card:
        await bot.send_message(chat_id, "ð ÐÐ°ÑÐ°Ð»Ð¾Ð³ Ð¿Ð¾ÐºÐ¸ ÑÐ¾ Ð¿Ð¾ÑÐ¾Ð¶Ð½ÑÐ¹.")
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


async def _edit_product_card(bot: Bot, chat_id: int, message_id: int, tenant_id: str, product_id: int) -> bool:
    card = await _build_product_card(tenant_id, product_id)
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
        return ("ð *ÐÐ¾ÑÐ¸Ðº*\n\nÐÐ¾ÑÐ¾Ð¶Ð½ÑÐ¾.", [])

    total = 0
    lines = ["ð *ÐÐ¾ÑÐ¸Ðº*\n"]
    for it in items:
        name = str(it["name"])
        qty = int(it["qty"])
        price = int(it.get("price_kop") or 0)
        total += price * qty
        lines.append(f"{name}\n{qty} Ã {_fmt_money(price)} = *{_fmt_money(price * qty)}*")
    lines.append(f"\nÐ Ð°Ð·Ð¾Ð¼: *{_fmt_money(total)}*")
    return ("\n\n".join(lines), items)


async def _send_cart(bot: Bot, chat_id: int, tenant_id: str, user_id: int, *, is_admin: bool) -> None:
    text, items = await _render_cart_text(tenant_id, user_id)
    await bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=cart_kb(is_admin=is_admin))
    if items:
        await bot.send_message(chat_id, "âï¸ ÐÐµÑÑÐ²Ð°Ð½Ð½Ñ ÐºÐ¾ÑÐ¸ÐºÐ¾Ð¼:", reply_markup=cart_inline(items=items))


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
            "ð§¾ *ÐÑÑÐ¾ÑÑÑ Ð·Ð°Ð¼Ð¾Ð²Ð»ÐµÐ½Ñ*\n\nÐÐ¾ÐºÐ¸ ÑÐ¾ Ð¿Ð¾ÑÐ¾Ð¶Ð½ÑÐ¾.",
            parse_mode="Markdown",
            reply_markup=orders_history_kb(is_admin=is_admin),
        )
        return

    lines = ["ð§¾ *ÐÑÑÐ¾ÑÑÑ Ð·Ð°Ð¼Ð¾Ð²Ð»ÐµÐ½Ñ*\n"]
    for o in orders:
        oid = int(o["id"])
        status = str(o["status"])
        total = int(o["total_kop"] or 0)
        lines.append(f"#{oid} â *{status}* â {_fmt_money(total)}")

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

        # â 1) Admin callbacks first
        if payload.startswith("tgadm:"):
            if not is_admin:
                cb_id = cb.get("id")
                if cb_id:
                    await bot.answer_callback_query(cb_id, text="â ÐÐµÐ¼Ð° Ð´Ð¾ÑÑÑÐ¿Ñ", show_alert=False)
                return True

            handled = await admin_handle_update(tenant=tenant, data=data, bot=bot)
            return bool(handled)

        # â 2) Shop callbacks
        if not payload.startswith("tgshop:"):
            return False

        cb_id = cb.get("id")
        msg_id = int(cb["message"]["message_id"])

        parts = payload.split(":")
        action = parts[1] if len(parts) > 1 else ""
        pid = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0

        if action == "noop":
            if cb_id:
                await bot.answer_callback_query(cb_id, text="â¢", show_alert=False)
            return True

        if action == "add" and pid > 0:
            await TelegramShopCartRepo.cart_inc(tenant_id, user_id, pid, 1)
            if cb_id:
                await bot.answer_callback_query(cb_id, text="â ÐÐ¾Ð´Ð°Ð½Ð¾ Ð² ÐºÐ¾ÑÐ¸Ðº", show_alert=False)
            return True

        if action == "fav" and pid > 0:
            if cb_id:
                await bot.answer_callback_query(cb_id, text="â­ ÐÐ¾Ð´Ð°Ð½Ð¾ Ð² Ð¾Ð±ÑÐ°Ð½Ðµ (ÑÐºÐ¾ÑÐ¾ Ð±ÑÐ´Ðµ Ð»Ð¾Ð³ÑÐºÐ°)", show_alert=False)
            return True

        if action == "prev" and pid > 0:
            p = await ProductsRepo.get_prev_active(tenant_id, pid)
            if not p:
                if cb_id:
                    await bot.answer_callback_query(cb_id, text="â¢", show_alert=False)
                return True
            await _edit_product_card(bot, chat_id, msg_id, tenant_id, int(p["id"]))
            if cb_id:
                await bot.answer_callback_query(cb_id)
            return True

        if action == "next" and pid > 0:
            p = await ProductsRepo.get_next_active(tenant_id, pid)
            if not p:
                if cb_id:
                    await bot.answer_callback_query(cb_id, text="â¢", show_alert=False)
                return True
            await _edit_product_card(bot, chat_id, msg_id, tenant_id, int(p["id"]))
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
                await bot.send_message(chat_id, "ð ÐÐ¾ÑÐ¸Ðº Ð¿Ð¾ÑÐ¾Ð¶Ð½ÑÐ¹ â Ð½ÑÑÐ¾Ð³Ð¾ Ð¾ÑÐ¾ÑÐ¼Ð»ÑÐ²Ð°ÑÐ¸.", reply_markup=cart_kb(is_admin=is_admin))
            else:
                await bot.send_message(chat_id, f"â ÐÐ°Ð¼Ð¾Ð²Ð»ÐµÐ½Ð½Ñ *#{oid}* ÑÑÐ²Ð¾ÑÐµÐ½Ð¾!", parse_mode="Markdown", reply_markup=main_menu_kb(is_admin=is_admin))
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

    # â Admin handler FIRST (so wizard can process photos/documents without text)
    if is_admin:
        handled = await admin_handle_update(tenant=tenant, data=data, bot=bot)
        if handled:
            return True

    # then text-based client buttons
    text = _get_text(msg)
    if not text:
        return False

    log.info("tgshop message text=%r user_id=%s tenant=%s", text, user_id, tenant_id)

    if text in ("/start", "/shop"):
        await _send_menu(bot, chat_id, "ð *ÐÐ°Ð³Ð°Ð·Ð¸Ð½*\n\nÐÐ±Ð¸ÑÐ°Ð¹ ÑÐ¾Ð·Ð´ÑÐ» ÐºÐ½Ð¾Ð¿ÐºÐ°Ð¼Ð¸ Ð½Ð¸Ð¶ÑÐµ ð", is_admin=is_admin)
        return True

    if text == _normalize_text(BTN_CATALOG):
        await _send_first_product_card(bot, chat_id, tenant_id, is_admin=is_admin)
        return True

    if text == _normalize_text(BTN_CART):
        await _send_cart(bot, chat_id, tenant_id, user_id, is_admin=is_admin)
        return True

    if text == _normalize_text(BTN_ORDERS):
        await _send_orders(bot, chat_id, tenant_id, user_id, is_admin=is_admin)
        return True

    if text == _normalize_text(BTN_HITS):
        await bot.send_message(chat_id, "ð¥ *Ð¥ÑÑÐ¸ / ÐÐºÑÑÑ*\n\nÐÐ¾ÐºÐ¸ ÑÐ¾ Ð² ÑÐ¾Ð·ÑÐ¾Ð±ÑÑ (Ð³Ð°ÑÐ¾Ðº Ð³Ð¾ÑÐ¾Ð²Ð¸Ð¹).", parse_mode="Markdown", reply_markup=catalog_kb(is_admin=is_admin))
        return True

    if text == _normalize_text(BTN_FAV):
        await bot.send_message(chat_id, "â­ *ÐÐ±ÑÐ°Ð½Ðµ*\n\nÐÐ¾ÐºÐ¸ ÑÐ¾ Ð² ÑÐ¾Ð·ÑÐ¾Ð±ÑÑ (Ð³Ð°ÑÐ¾Ðº Ð³Ð¾ÑÐ¾Ð²Ð¸Ð¹).", parse_mode="Markdown", reply_markup=favorites_kb(is_admin=is_admin))
        return True

    if text == _normalize_text(BTN_SUPPORT):
        await bot.send_message(chat_id, "ð *ÐÑÐ´ÑÑÐ¸Ð¼ÐºÐ°*\n\nÐÐ¾ÐºÐ¸ ÑÐ¾ Ð² ÑÐ¾Ð·ÑÐ¾Ð±ÑÑ (Ð³Ð°ÑÐ¾Ðº Ð³Ð¾ÑÐ¾Ð²Ð¸Ð¹).", parse_mode="Markdown", reply_markup=support_kb(is_admin=is_admin))
        return True

    if text == _normalize_text(BTN_MENU_BACK):
        await _send_menu(bot, chat_id, "â¬ï¸ ÐÐ¾Ð²ÐµÑÐ½ÑÐ² Ñ Ð¼ÐµÐ½Ñ ð", is_admin=is_admin)
        return True

    if text == _normalize_text(BTN_CLEAR_CART):
        await TelegramShopCartRepo.cart_clear(tenant_id, user_id)
        await _send_cart(bot, chat_id, tenant_id, user_id, is_admin=is_admin)
        return True

    if text == _normalize_text(BTN_CHECKOUT):
        oid = await TelegramShopOrdersRepo.create_order_from_cart(tenant_id, user_id)
        if not oid:
            await bot.send_message(chat_id, "ð ÐÐ¾ÑÐ¸Ðº Ð¿Ð¾ÑÐ¾Ð¶Ð½ÑÐ¹ â Ð½ÑÑÐ¾Ð³Ð¾ Ð¾ÑÐ¾ÑÐ¼Ð»ÑÐ²Ð°ÑÐ¸.", reply_markup=cart_kb(is_admin=is_admin))
        else:
            await bot.send_message(chat_id, f"â ÐÐ°Ð¼Ð¾Ð²Ð»ÐµÐ½Ð½Ñ *#{oid}* ÑÑÐ²Ð¾ÑÐµÐ½Ð¾!", parse_mode="Markdown", reply_markup=main_menu_kb(is_admin=is_admin))
        return True

    if text == _normalize_text(BTN_ADMIN) and is_admin:
        await bot.send_message(chat_id, "ð  ÐÐ´Ð¼ÑÐ½ÐºÐ°: /a_help", reply_markup=main_menu_kb(is_admin=True))
        return True

    return False
