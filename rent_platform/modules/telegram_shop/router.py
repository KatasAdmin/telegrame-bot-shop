from __future__ import annotations

import logging
from typing import Any

from aiogram import Bot

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
from rent_platform.modules.telegram_shop.ui.inline_kb import catalog_inline, cart_inline

log = logging.getLogger(__name__)


def _extract_message(update: dict) -> dict | None:
    return update.get("message") or update.get("edited_message")


def _extract_callback(update: dict) -> dict | None:
    return update.get("callback_query")


def _get_text(msg: dict) -> str:
    return (msg.get("text") or "").strip()


def _get_chat_id_from_msg(msg: dict) -> int:
    return int(msg["chat"]["id"])


def _get_user_id_from_msg(msg: dict) -> int:
    return int(msg["from"]["id"])


def _get_chat_id_from_cb(cb: dict) -> int:
    return int(cb["message"]["chat"]["id"])


def _get_message_id_from_cb(cb: dict) -> int:
    return int(cb["message"]["message_id"])


def _get_user_id_from_cb(cb: dict) -> int:
    return int(cb["from"]["id"])


def _fmt_money(kop: int) -> str:
    kop = int(kop or 0)
    грн = kop // 100
    коп = kop % 100
    return f"{грн}.{коп:02d} грн"


async def _send_menu(bot: Bot, chat_id: int, text: str, *, is_admin: bool) -> None:
    await bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=main_menu_kb(is_admin=is_admin))


async def _render_catalog_text(tenant_id: str) -> tuple[str, list[int]]:
    items = await ProductsRepo.list_active(tenant_id, limit=10)
    if not items:
        return ("🛍 *Каталог*\n\nПоки що немає товарів.", [])

    lines = ["🛍 *Каталог*\n"]
    ids: list[int] = []
    for p in items:
        pid = int(p["id"])
        ids.append(pid)
        name = str(p["name"])
        price = int(p.get("price_kop") or 0)
        lines.append(f"*{pid})* {name}\n{_fmt_money(price)}")
    lines.append("\nНатискай ➕ біля товару, щоб додати в кошик 👇")
    return ("\n\n".join(lines), ids)


async def _send_catalog(bot: Bot, chat_id: int, tenant_id: str, *, is_admin: bool) -> None:
    text, ids = await _render_catalog_text(tenant_id)
    await bot.send_message(
        chat_id,
        text,
        parse_mode="Markdown",
        reply_markup=catalog_kb(is_admin=is_admin),
    )
    # окремим повідомленням — inline список дій (щоб reply kb не заважала)
    if ids:
        await bot.send_message(chat_id, "🧾 Додай товари кнопками:", reply_markup=catalog_inline(product_ids=ids))


async def _render_cart_text(tenant_id: str, user_id: int) -> tuple[str, list[dict]]:
    items = await TelegramShopCartRepo.cart_list(tenant_id, user_id)
    if not items:
        return ("🛒 *Кошик*\n\nПорожньо.", [])

    total = 0
    lines = ["🛒 *Кошик*\n"]
    for it in items:
        pid = int(it["product_id"])
        name = str(it["name"])
        qty = int(it["qty"])
        price = int(it.get("price_kop") or 0)
        total += price * qty
        lines.append(f"*{pid})* {name}\n{qty} × {_fmt_money(price)} = *{_fmt_money(price * qty)}*")
    lines.append(f"\nРазом: *{_fmt_money(total)}*")
    lines.append("\nКеруй кількістю кнопками нижче 👇")
    return ("\n\n".join(lines), items)


async def _send_cart(bot: Bot, chat_id: int, tenant_id: str, user_id: int, *, is_admin: bool) -> None:
    text, items = await _render_cart_text(tenant_id, user_id)
    await bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=cart_kb(is_admin=is_admin))
    if items:
        await bot.send_message(chat_id, "⚙️ Кошик (керування):", reply_markup=cart_inline(items=items))


async def _edit_cart_inline(bot: Bot, chat_id: int, message_id: int, tenant_id: str, user_id: int) -> None:
    text, items = await _render_cart_text(tenant_id, user_id)
    # якщо кошик став порожній — просто редагуємо повідомлення і прибираємо клаву
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
        text = "🧾 *Історія замовлень*\n\nПоки що порожньо."
    else:
        lines = ["🧾 *Історія замовлень*\n"]
        for o in orders:
            oid = int(o["id"])
            status = str(o["status"])
            total = int(o["total_kop"] or 0)
            lines.append(f"#{oid} — *{status}* — {_fmt_money(total)}")
        text = "\n".join(lines)

    await bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=orders_history_kb(is_admin=is_admin))


async def handle_update(tenant: dict, data: dict[str, Any], bot: Bot) -> bool:
    tenant_id = str(tenant["id"])

    # --- callback queries (inline buttons) ---
    cb = _extract_callback(data)
    if cb:
        user_id = _get_user_id_from_cb(cb)
        chat_id = _get_chat_id_from_cb(cb)
        msg_id = _get_message_id_from_cb(cb)
        is_admin = is_admin_user(tenant=tenant, user_id=user_id)

        # acknowledge to stop spinner
        cb_id = cb.get("id")
        if cb_id:
            await bot.answer_callback_query(cb_id)

        payload = (cb.get("data") or "").strip()
        # expected: tgshop:<action>:<id?>
        if not payload.startswith("tgshop:"):
            return False

        parts = payload.split(":")
        action = parts[1] if len(parts) > 1 else ""
        pid = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0

        if action == "noop":
            return True

        if action == "catalog":
            # just send catalog again
            await _send_catalog(bot, chat_id, tenant_id, is_admin=is_admin)
            return True

        if action == "cart":
            await _send_cart(bot, chat_id, tenant_id, user_id, is_admin=is_admin)
            return True

        if action == "add" and pid > 0:
            await TelegramShopCartRepo.cart_inc(tenant_id, user_id, pid, 1)
            # show updated cart inline (edit the inline message if it's cart control),
            # but here we might be on catalog message => just send cart
            await _send_cart(bot, chat_id, tenant_id, user_id, is_admin=is_admin)
            return True

        if action in {"inc", "dec", "del", "clear", "checkout"}:
            if action == "inc" and pid > 0:
                await TelegramShopCartRepo.cart_inc(tenant_id, user_id, pid, 1)
                await _edit_cart_inline(bot, chat_id, msg_id, tenant_id, user_id)
                return True

            if action == "dec" and pid > 0:
                await TelegramShopCartRepo.cart_inc(tenant_id, user_id, pid, -1)
                await _edit_cart_inline(bot, chat_id, msg_id, tenant_id, user_id)
                return True

            if action == "del" and pid > 0:
                await TelegramShopCartRepo.cart_delete_item(tenant_id, user_id, pid)
                await _edit_cart_inline(bot, chat_id, msg_id, tenant_id, user_id)
                return True

            if action == "clear":
                await TelegramShopCartRepo.cart_clear(tenant_id, user_id)
                await _edit_cart_inline(bot, chat_id, msg_id, tenant_id, user_id)
                return True

            if action == "checkout":
                oid = await TelegramShopOrdersRepo.create_order_from_cart(tenant_id, user_id)
                if not oid:
                    await bot.send_message(chat_id, "🛒 Кошик порожній — нічого оформлювати.", reply_markup=cart_kb(is_admin=is_admin))
                else:
                    await bot.send_message(chat_id, f"✅ Замовлення *#{oid}* створено!", parse_mode="Markdown", reply_markup=main_menu_kb(is_admin=is_admin))
                # refresh inline cart message too
                await _edit_cart_inline(bot, chat_id, msg_id, tenant_id, user_id)
                return True

        return False

    # --- messages (reply keyboard buttons + commands like /shop) ---
    msg = _extract_message(data)
    if not msg:
        return False

    text = _get_text(msg)
    if not text:
        return False

    chat_id = _get_chat_id_from_msg(msg)
    user_id = _get_user_id_from_msg(msg)
    is_admin = is_admin_user(tenant=tenant, user_id=user_id)

    # --- Admin hook (kept as hook; client won't see commands) ---
    if is_admin:
        handled = await admin_handle_update(tenant=tenant, data=data, bot=bot)
        if handled:
            return True

    # commands
    if text in ("/start", "/shop"):
        await _send_menu(bot, chat_id, "🛒 *Магазин*\n\nОбирай розділ кнопками нижче 👇", is_admin=is_admin)
        return True

    if text == "/products":
        await _send_catalog(bot, chat_id, tenant_id, is_admin=is_admin)
        return True

    if text == "/orders":
        await _send_orders(bot, chat_id, tenant_id, user_id, is_admin=is_admin)
        return True

    # menu buttons (client only)
    if text == BTN_CATALOG:
        await _send_catalog(bot, chat_id, tenant_id, is_admin=is_admin)
        return True

    if text == BTN_CART:
        await _send_cart(bot, chat_id, tenant_id, user_id, is_admin=is_admin)
        return True

    if text == BTN_HITS:
        await bot.send_message(
            chat_id,
            "🔥 *Хіти / Акції*\n\nПоки що в розробці (буде після міграцій promo/hit).",
            parse_mode="Markdown",
            reply_markup=catalog_kb(is_admin=is_admin),
        )
        return True

    if text == BTN_FAV:
        await bot.send_message(
            chat_id,
            "⭐ *Обране*\n\nПоки що в розробці.",
            parse_mode="Markdown",
            reply_markup=favorites_kb(is_admin=is_admin),
        )
        return True

    if text == BTN_ORDERS:
        await _send_orders(bot, chat_id, tenant_id, user_id, is_admin=is_admin)
        return True

    if text == BTN_SUPPORT:
        await bot.send_message(
            chat_id,
            "🆘 *Підтримка*\n\nПоки що в розробці.",
            parse_mode="Markdown",
            reply_markup=support_kb(is_admin=is_admin),
        )
        return True

    if text == BTN_MENU_BACK:
        await _send_menu(bot, chat_id, "⬅️ Повернув у меню 👇", is_admin=is_admin)
        return True

    # reply-keyboard cart buttons (client)
    if text == BTN_CLEAR_CART:
        await TelegramShopCartRepo.cart_clear(tenant_id, user_id)
        await _send_cart(bot, chat_id, tenant_id, user_id, is_admin=is_admin)
        return True

    if text == BTN_CHECKOUT:
        oid = await TelegramShopOrdersRepo.create_order_from_cart(tenant_id, user_id)
        if not oid:
            await bot.send_message(chat_id, "🛒 Кошик порожній — нічого оформлювати.", reply_markup=cart_kb(is_admin=is_admin))
        else:
            await bot.send_message(chat_id, f"✅ Замовлення *#{oid}* створено!", parse_mode="Markdown", reply_markup=main_menu_kb(is_admin=is_admin))
        return True

    if text == BTN_ADMIN and is_admin:
        await bot.send_message(chat_id, "🛠 Адмінка: напиши /a_help", reply_markup=main_menu_kb(is_admin=True))
        return True

    return False