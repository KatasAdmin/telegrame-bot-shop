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
from rent_platform.modules.telegram_shop.ui.inline_kb import product_card_kb, cart_inline

log = logging.getLogger(__name__)


def _extract_message(update: dict) -> dict | None:
    return update.get("message") or update.get("edited_message")


def _extract_callback(update: dict) -> dict | None:
    return update.get("callback_query")


def _get_text(msg: dict) -> str:
    return (msg.get("text") or "").strip()


def _fmt_money(kop: int) -> str:
    kop = int(kop or 0)
    грн = kop // 100
    коп = kop % 100
    return f"{грн}.{коп:02d} грн"


async def _send_menu(bot: Bot, chat_id: int, text: str, *, is_admin: bool) -> None:
    await bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=main_menu_kb(is_admin=is_admin))


async def _send_product_card(bot: Bot, chat_id: int, tenant_id: str, product_id: int, *, is_admin: bool) -> None:
    p = await ProductsRepo.get_active(tenant_id, product_id)
    if not p:
        await bot.send_message(chat_id, "Товар не знайдено або він не активний.")
        return

    prev_p = await ProductsRepo.get_prev_active(tenant_id, product_id)
    next_p = await ProductsRepo.get_next_active(tenant_id, product_id)

    pid = int(p["id"])
    name = str(p["name"])
    price = int(p.get("price_kop") or 0)

    # TODO hooks for photos/description later:
    # - photos (up to 10)
    # - description text
    text = f"🛍 *{name}*\n\nЦіна: *{_fmt_money(price)}*\n\nID: `{pid}`"

    await bot.send_message(
        chat_id,
        text,
        parse_mode="Markdown",
        reply_markup=product_card_kb(product_id=pid, has_prev=bool(prev_p), has_next=bool(next_p)),
    )


async def _send_first_product(bot: Bot, chat_id: int, tenant_id: str, *, is_admin: bool) -> None:
    p = await ProductsRepo.get_first_active(tenant_id)
    if not p:
        await bot.send_message(chat_id, "🛍 *Каталог*\n\nПоки що немає товарів.", parse_mode="Markdown", reply_markup=catalog_kb(is_admin=is_admin))
        return
    await _send_product_card(bot, chat_id, tenant_id, int(p["id"]), is_admin=is_admin)


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
    await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode="Markdown", reply_markup=cart_inline(items=items))


async def _send_orders(bot: Bot, chat_id: int, tenant_id: str, user_id: int, *, is_admin: bool) -> None:
    orders = await TelegramShopOrdersRepo.list_orders(tenant_id, user_id, limit=20)
    if not orders:
        await bot.send_message(chat_id, "🧾 *Історія замовлень*\n\nПоки що порожньо.", parse_mode="Markdown", reply_markup=orders_history_kb(is_admin=is_admin))
        return

    lines = ["🧾 *Історія замовлень*\n"]
    for o in orders:
        oid = int(o["id"])
        status = str(o["status"])
        total = int(o["total_kop"] or 0)
        lines.append(f"#{oid} — *{status}* — {_fmt_money(total)}")

    await bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown", reply_markup=orders_history_kb(is_admin=is_admin))


async def handle_update(tenant: dict, data: dict[str, Any], bot: Bot) -> bool:
    tenant_id = str(tenant["id"])

    # --- callback queries (inline buttons) ---
    cb = _extract_callback(data)
    if cb:
        cb_id = cb.get("id")
        if cb_id:
            await bot.answer_callback_query(cb_id)

        payload = (cb.get("data") or "").strip()
        if not payload.startswith("tgshop:"):
            return False

        chat_id = int(cb["message"]["chat"]["id"])
        msg_id = int(cb["message"]["message_id"])
        user_id = int(cb["from"]["id"])
        is_admin = is_admin_user(tenant=tenant, user_id=user_id)

        parts = payload.split(":")
        action = parts[1] if len(parts) > 1 else ""
        pid = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0

        if action == "noop":
            return True

        # add to cart WITHOUT redirect to cart
        if action == "add" and pid > 0:
            await TelegramShopCartRepo.cart_inc(tenant_id, user_id, pid, 1)
            # show a toast
            await bot.answer_callback_query(cb_id, text="✅ Додано в кошик", show_alert=False)
            return True

        # favorites hook (later)
        if action == "fav" and pid > 0:
            await bot.answer_callback_query(cb_id, text="⭐ Обране (скоро)", show_alert=False)
            return True

        # product navigation
        if action == "prev" and pid > 0:
            p = await ProductsRepo.get_prev_active(tenant_id, pid)
            if not p:
                await bot.answer_callback_query(cb_id, text="Немає попереднього", show_alert=False)
                return True
            # send next card (simple) — later we can edit message instead of spamming
            await _send_product_card(bot, chat_id, tenant_id, int(p["id"]), is_admin=is_admin)
            return True

        if action == "next" and pid > 0:
            p = await ProductsRepo.get_next_active(tenant_id, pid)
            if not p:
                await bot.answer_callback_query(cb_id, text="Немає наступного", show_alert=False)
                return True
            await _send_product_card(bot, chat_id, tenant_id, int(p["id"]), is_admin=is_admin)
            return True

        if action == "cart":
            await _send_cart(bot, chat_id, tenant_id, user_id, is_admin=is_admin)
            return True

        # cart controls (qty already works)
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
            await _edit_cart_inline(bot, chat_id, msg_id, tenant_id, user_id)
            return True

        return False

    # --- messages (reply keyboard) ---
    msg = _extract_message(data)
    if not msg:
        return False

    text = _get_text(msg)
    if not text:
        return False

    chat_id = int(msg["chat"]["id"])
    user_id = int(msg["from"]["id"])
    is_admin = is_admin_user(tenant=tenant, user_id=user_id)

    # keep admin hooks (client won't use commands)
    if is_admin:
        handled = await admin_handle_update(tenant=tenant, data=data, bot=bot)
        if handled:
            return True

    if text in ("/start", "/shop"):
        await _send_menu(bot, chat_id, "🛒 *Магазин*\n\nОбирай розділ кнопками нижче 👇", is_admin=is_admin)
        return True

    if text == BTN_CATALOG:
        await _send_first_product(bot, chat_id, tenant_id, is_admin=is_admin)
        return True

    if text == BTN_CART:
        await _send_cart(bot, chat_id, tenant_id, user_id, is_admin=is_admin)
        return True

    if text == BTN_ORDERS:
        await _send_orders(bot, chat_id, tenant_id, user_id, is_admin=is_admin)
        return True

    if text == BTN_HITS:
        await bot.send_message(chat_id, "🔥 *Хіти / Акції*\n\nПоки що в розробці.", parse_mode="Markdown", reply_markup=catalog_kb(is_admin=is_admin))
        return True

    if text == BTN_FAV:
        await bot.send_message(chat_id, "⭐ *Обране*\n\nПоки що в розробці.", parse_mode="Markdown", reply_markup=favorites_kb(is_admin=is_admin))
        return True

    if text == BTN_SUPPORT:
        await bot.send_message(chat_id, "🆘 *Підтримка*\n\nПоки що в розробці.", parse_mode="Markdown", reply_markup=support_kb(is_admin=is_admin))
        return True

    if text == BTN_MENU_BACK:
        await _send_menu(bot, chat_id, "⬅️ Повернув у меню 👇", is_admin=is_admin)
        return True

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
        await bot.send_message(chat_id, "🛠 Адмінка: /a_help", reply_markup=main_menu_kb(is_admin=True))
        return True

    return False