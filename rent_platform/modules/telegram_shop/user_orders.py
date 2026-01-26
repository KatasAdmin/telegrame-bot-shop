# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as _dt
from typing import Any

from aiogram import Bot

from rent_platform.modules.telegram_shop.repo.orders import TelegramShopOrdersRepo
from rent_platform.modules.telegram_shop.repo.orders_archive import TelegramShopOrdersArchiveRepo
from rent_platform.modules.telegram_shop.ui.inline_orders_kb import (
    orders_list_kb,
    order_detail_kb,
    order_items_kb,
)
from rent_platform.modules.telegram_shop.ui.orders_status import status_label


def _fmt_money(kop: int) -> str:
    kop = int(kop or 0)
    return f"{kop // 100}.{kop % 100:02d} грн"


def _fmt_dt(ts: int) -> str:
    ts = int(ts or 0)
    if ts <= 0:
        return "—"
    return _dt.datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M")


async def send_orders_list(bot: Bot, chat_id: int, tenant_id: str, user_id: int) -> None:
    orders = await TelegramShopOrdersRepo.list_orders(tenant_id, user_id, limit=20)
    orders = orders or []

    if not orders:
        await bot.send_message(chat_id, "🧾 *Історія замовлень*\n\nПоки що порожньо.", parse_mode="Markdown")
        return

    lines = ["🧾 *Історія замовлень*\n"]
    ids: list[int] = []

    for o in orders:
        oid = int(o.get("id") or 0)
        if oid <= 0:
            continue
        ids.append(oid)

        st = status_label(str(o.get("status") or ""))
        total = _fmt_money(int(o.get("total_kop") or 0))
        created = _fmt_dt(int(o.get("created_ts") or 0))
        lines.append(f"• #{oid} — {st} — *{total}* — _{created}_")

    await bot.send_message(
        chat_id,
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=orders_list_kb(ids),
    )


async def send_order_detail(bot: Bot, chat_id: int, tenant_id: str, user_id: int, order_id: int) -> None:
    o = await TelegramShopOrdersRepo.get_order(tenant_id, int(order_id))
    if not o:
        await bot.send_message(chat_id, "Замовлення не знайдено 😅")
        return

    # ✅ security: чужі замовлення не показуємо
    if int(o.get("user_id") or 0) != int(user_id):
        await bot.send_message(chat_id, "⛔ Це замовлення не належить вам.")
        return

    oid = int(o.get("id") or 0)
    st = status_label(str(o.get("status") or ""))
    total = _fmt_money(int(o.get("total_kop") or 0))
    created = _fmt_dt(int(o.get("created_ts") or 0))

    is_arch = await TelegramShopOrdersArchiveRepo.is_archived(tenant_id, user_id, oid)

    text = (
        f"🧾 *Замовлення #{oid}*\n\n"
        f"Статус: *{st}*\n"
        f"Сума: *{total}*\n"
        f"Створено: _{created}_\n\n"
        f"_(Далі додамо таймлайн: прийнято/зiбрано/НП/отримано/не отримано/повернення/скасовано…)_\n"
    )

    await bot.send_message(
        chat_id,
        text,
        parse_mode="Markdown",
        reply_markup=order_detail_kb(oid, is_archived=bool(is_arch)),
    )


async def send_order_items(bot: Bot, chat_id: int, tenant_id: str, user_id: int, order_id: int) -> None:
    o = await TelegramShopOrdersRepo.get_order(tenant_id, int(order_id))
    if not o:
        await bot.send_message(chat_id, "Замовлення не знайдено 😅")
        return

    # ✅ security
    if int(o.get("user_id") or 0) != int(user_id):
        await bot.send_message(chat_id, "⛔ Це замовлення не належить вам.")
        return

    items = await TelegramShopOrdersRepo.list_order_items(int(order_id))
    items = items or []

    if not items:
        await bot.send_message(
            chat_id,
            f"📦 *Товари в замовленні #{int(order_id)}*\n\nПоки що порожньо.",
            parse_mode="Markdown",
            reply_markup=order_items_kb(int(order_id)),
        )
        return

    lines = [f"📦 *Товари в замовленні #{int(order_id)}*\n"]
    for it in items:
        name = str(it.get("name") or f"Товар #{it.get('product_id')}")
        qty = int(it.get("qty") or 0)
        price = _fmt_money(int(it.get("price_kop") or 0))
        lines.append(f"• *{name}* — {qty} шт × {price}")

    await bot.send_message(
        chat_id,
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=order_items_kb(int(order_id)),
    )


async def handle_orders_callback(
    *,
    bot: Bot,
    tenant_id: str,
    user_id: int,
    chat_id: int,
    payload: str,
) -> bool:
    if not payload.startswith("tgord:"):
        return False

    parts = payload.split(":")
    action = parts[1] if len(parts) > 1 else ""
    raw = parts[2] if len(parts) > 2 else "0"

    if action == "list":
        await send_orders_list(bot, chat_id, tenant_id, user_id)
        return True

    if action == "open":
        oid = int(raw) if raw.isdigit() else 0
        if oid > 0:
            await send_order_detail(bot, chat_id, tenant_id, user_id, oid)
        return True

    if action == "items":
        oid = int(raw) if raw.isdigit() else 0
        if oid > 0:
            await send_order_items(bot, chat_id, tenant_id, user_id, oid)
        return True

    if action == "arch":
        oid = int(raw) if raw.isdigit() else 0
        if oid > 0:
            await TelegramShopOrdersArchiveRepo.toggle(tenant_id, user_id, oid)
            await send_order_detail(bot, chat_id, tenant_id, user_id, oid)
        return True

    return True