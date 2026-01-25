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

log = logging.getLogger(__name__)


def _extract_message(update: dict) -> dict | None:
    return update.get("message") or update.get("edited_message")


def _get_text(msg: dict) -> str:
    return (msg.get("text") or "").strip()


def _get_chat_id(msg: dict) -> int:
    return int(msg["chat"]["id"])


def _get_user_id(msg: dict) -> int:
    return int(msg["from"]["id"])


def _fmt_money(kop: int) -> str:
    kop = int(kop or 0)
    грн = kop // 100
    коп = kop % 100
    return f"{грн}.{коп:02d} грн"


async def _send_menu(bot: Bot, chat_id: int, text: str, *, is_admin: bool) -> None:
    await bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=main_menu_kb(is_admin=is_admin))


async def _show_catalog(bot: Bot, chat_id: int, tenant_id: str, *, is_admin: bool) -> None:
    items = await ProductsRepo.list_active(tenant_id, limit=20)
    if not items:
        text = "🛍 *Каталог*\n\nПоки що немає товарів."
    else:
        lines = ["🛍 *Каталог*\n"]
        for p in items[:20]:
            pid = int(p["id"])
            name = str(p["name"])
            price = int(p.get("price_kop") or 0)
            lines.append(f"*{pid})* {name}\n{_fmt_money(price)}")
        lines.append("\n➕ Додати в кошик: `+ <id>` (наприклад `+ 12`)")
        lines.append("➖ Зменшити: `- <id>` | 🗑 Видалити: `del <id>`")
        text = "\n\n".join(lines)

    await bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=catalog_kb(is_admin=is_admin))


async def _show_cart(bot: Bot, chat_id: int, tenant_id: str, user_id: int, *, is_admin: bool) -> None:
    items = await TelegramShopCartRepo.cart_list(tenant_id, user_id)
    if not items:
        text = "🛒 *Кошик*\n\nПорожньо."
    else:
        lines = ["🛒 *Кошик*\n"]
        total = 0
        for it in items:
            pid = int(it["product_id"])
            name = str(it["name"])
            qty = int(it["qty"])
            price = int(it.get("price_kop") or 0)
            total += price * qty
            lines.append(f"*{pid})* {name}\n{qty} × {_fmt_money(price)} = *{_fmt_money(price * qty)}*")
        lines.append(f"\nРазом: *{_fmt_money(total)}*")
        lines.append("\n➕ `+ <id>`  ➖ `- <id>`  🗑 `del <id>`")
        text = "\n\n".join(lines)

    await bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=cart_kb(is_admin=is_admin))


async def _show_orders_history(bot: Bot, chat_id: int, tenant_id: str, user_id: int, *, is_admin: bool) -> None:
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
    msg = _extract_message(data)
    if not msg:
        return False

    text = _get_text(msg)
    if not text:
        return False

    tenant_id = str(tenant["id"])
    chat_id = _get_chat_id(msg)
    user_id = _get_user_id(msg)
    is_admin = is_admin_user(tenant=tenant, user_id=user_id)

    # --- Admin hook (separate module) ---
    if is_admin:
        handled = await admin_handle_update(tenant=tenant, data=data, bot=bot)
        if handled:
            return True

    # commands
    if text in ("/start", "/shop"):
        await _send_menu(bot, chat_id, "🛒 *Магазин*\n\nОбирай розділ кнопками нижче 👇", is_admin=is_admin)
        return True

    if text == "/products":
        await _show_catalog(bot, chat_id, tenant_id, is_admin=is_admin)
        return True

    if text == "/orders":
        await _show_orders_history(bot, chat_id, tenant_id, user_id, is_admin=is_admin)
        return True

    # cart text commands: "+ 12", "- 12", "del 12"
    parts = text.split()
    if len(parts) == 2 and parts[0] in {"+", "-", "del"} and parts[1].isdigit():
        pid = int(parts[1])
        if parts[0] == "del":
            await TelegramShopCartRepo.cart_delete_item(tenant_id, user_id, pid)
        else:
            delta = 1 if parts[0] == "+" else -1
            await TelegramShopCartRepo.cart_inc(tenant_id, user_id, pid, delta)

        await _show_cart(bot, chat_id, tenant_id, user_id, is_admin=is_admin)
        return True

    # menu buttons
    if text == BTN_CATALOG:
        await _show_catalog(bot, chat_id, tenant_id, is_admin=is_admin)
        return True

    if text == BTN_CART:
        await _show_cart(bot, chat_id, tenant_id, user_id, is_admin=is_admin)
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
        await _show_orders_history(bot, chat_id, tenant_id, user_id, is_admin=is_admin)
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

    # cart buttons
    if text == BTN_CLEAR_CART:
        await TelegramShopCartRepo.cart_clear(tenant_id, user_id)
        await _show_cart(bot, chat_id, tenant_id, user_id, is_admin=is_admin)
        return True

    if text == BTN_CHECKOUT:
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

    if text == BTN_ADMIN and is_admin:
        await bot.send_message(chat_id, "🛠 Адмінка: напиши /a_help", reply_markup=main_menu_kb(is_admin=True))
        return True

    return False