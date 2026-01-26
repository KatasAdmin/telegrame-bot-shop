# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as _dt
from typing import Any

from aiogram import Bot

from rent_platform.db.session import db_fetch_all, db_fetch_one, db_execute
from rent_platform.modules.telegram_shop.repo.orders import TelegramShopOrdersRepo

try:
    from rent_platform.modules.telegram_shop.ui.orders_status import status_label  # type: ignore
except Exception:  # pragma: no cover
    status_label = None  # type: ignore


PAGE_SIZE = 10


def _kb(rows: list[list[tuple[str, str]]]) -> dict:
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for (t, d) in row] for row in rows]}


def _fmt_money(kop: int) -> str:
    kop = int(kop or 0)
    return f"{kop // 100}.{kop % 100:02d} грн"


def _fmt_dt(ts: int) -> str:
    ts = int(ts or 0)
    if ts <= 0:
        return "—"
    return _dt.datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M")


def _st_label(st: str) -> str:
    st = (st or "").strip()
    if status_label:
        try:
            return str(status_label(st))
        except Exception:
            pass
    return st or "—"


STATUSES: list[tuple[str, str]] = [
    ("new", "🆕 Створено"),
    ("accepted", "✅ Прийнято"),
    ("packed", "📦 Зібрано"),
    ("shipped", "🚚 Відправлено"),
    ("delivered", "📬 Отримано"),
    ("not_received", "⛔ Не отримано"),
    ("returned", "↩️ Повернення"),
    ("cancelled", "❌ Скасовано"),
]


async def _send_or_edit(
    bot: Bot,
    *,
    chat_id: int,
    text: str,
    message_id: int | None,
    reply_markup: Any | None = None,
) -> None:
    if message_id:
        try:
            await bot.edit_message_text(
                text,
                chat_id=chat_id,
                message_id=int(message_id),
                parse_mode="Markdown",
                reply_markup=reply_markup,
            )
            return
        except Exception:
            pass

    await bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=reply_markup)


async def _list_orders_page(tenant_id: str, *, page: int) -> list[dict]:
    page = max(0, int(page or 0))
    offset = page * PAGE_SIZE
    q = """
    SELECT id, user_id, status, total_kop, created_ts
    FROM telegram_shop_orders
    WHERE tenant_id = $1
    ORDER BY id DESC
    LIMIT $2 OFFSET $3
    """
    rows = await db_fetch_all(q, tenant_id, PAGE_SIZE, offset)
    return rows or []


async def _count_orders(tenant_id: str) -> int:
    q = "SELECT COUNT(*) AS cnt FROM telegram_shop_orders WHERE tenant_id = $1"
    row = await db_fetch_one(q, tenant_id)
    return int((row or {}).get("cnt") or 0)


def _orders_list_kb(order_ids: list[int], *, page: int, has_prev: bool, has_next: bool) -> dict:
    rows: list[list[tuple[str, str]]] = []

    for oid in order_ids:
        rows.append([(f"🧾 Замовлення #{oid}", f"tgadm:ord_open:{oid}:{page}")])

    nav: list[tuple[str, str]] = []
    nav.append(("⬅️", f"tgadm:ord_list:{page-1}") if has_prev else ("·", "tgadm:noop:0"))
    nav.append(("➡️", f"tgadm:ord_list:{page+1}") if has_next else ("·", "tgadm:noop:0"))
    rows.append(nav)

    rows.append([("⬅️ В адмін-меню", "tgadm:home:0")])
    return _kb(rows)


def _order_detail_kb(order_id: int, *, page: int) -> dict:
    return _kb(
        [
            [("📦 Товари", f"tgadm:ord_items:{order_id}:{page}")],
            [("✏️ Змінити статус", f"tgadm:ord_status_menu:{order_id}:{page}")],
            [("⬅️ Назад", f"tgadm:ord_list:{page}")],
        ]
    )


def _order_items_kb(order_id: int, *, page: int) -> dict:
    return _kb([[("⬅️ Назад", f"tgadm:ord_open:{order_id}:{page}")]])


def _order_status_menu_kb(order_id: int, *, page: int) -> dict:
    rows: list[list[tuple[str, str]]] = []
    for st, title in STATUSES:
        rows.append([(title, f"tgadm:ord_setst:{order_id}:{st}:{page}")])
    rows.append([("⬅️ Назад", f"tgadm:ord_open:{order_id}:{page}")])
    return _kb(rows)


async def _send_admin_orders_menu(bot: Bot, chat_id: int, *, message_id: int | None) -> None:
    kb = _kb(
        [
            [("🧾 Останні замовлення", "tgadm:ord_list:0")],
            [("⬅️ В адмін-меню", "tgadm:home:0")],
        ]
    )
    await _send_or_edit(
        bot,
        chat_id=chat_id,
        message_id=message_id,
        text="🧾 *Адмін — Замовлення*\n\nОбери дію 👇",
        reply_markup=kb,
    )


async def _send_orders_list(bot: Bot, chat_id: int, tenant_id: str, *, page: int, message_id: int | None) -> None:
    page = max(0, int(page or 0))
    total = await _count_orders(tenant_id)
    rows = await _list_orders_page(tenant_id, page=page)

    if not rows:
        await _send_or_edit(
            bot,
            chat_id=chat_id,
            message_id=message_id,
            text="🧾 *Замовлення*\n\nПоки що порожньо.",
            reply_markup=_kb([[("⬅️ В адмін-меню", "tgadm:home:0")]]),
        )
        return

    order_ids: list[int] = [int(r["id"]) for r in rows if int(r.get("id") or 0) > 0]
    shown_from = page * PAGE_SIZE + 1
    shown_to = page * PAGE_SIZE + len(order_ids)

    lines = [f"🧾 *Замовлення* (показано {shown_from}-{shown_to} із {total})\n"]
    for r in rows:
        oid = int(r.get("id") or 0)
        st = _st_label(str(r.get("status") or ""))
        total_uah = _fmt_money(int(r.get("total_kop") or 0))
        created = _fmt_dt(int(r.get("created_ts") or 0))
        lines.append(f"• #{oid} — {st} — *{total_uah}* — _{created}_")

    has_prev = page > 0
    has_next = shown_to < total

    await _send_or_edit(
        bot,
        chat_id=chat_id,
        message_id=message_id,
        text="\n".join(lines),
        reply_markup=_orders_list_kb(order_ids, page=page, has_prev=has_prev, has_next=has_next),
    )


async def _send_order_detail(
    bot: Bot,
    chat_id: int,
    tenant_id: str,
    order_id: int,
    *,
    page: int,
    message_id: int | None,
) -> None:
    o = await TelegramShopOrdersRepo.get_order(tenant_id, int(order_id))
    if not o:
        await _send_or_edit(
            bot,
            chat_id=chat_id,
            message_id=message_id,
            text="🧾 *Замовлення*\n\nНе знайдено 😅",
            reply_markup=_kb([[("⬅️ Назад", f"tgadm:ord_list:{page}")]]),
        )
        return

    oid = int(o.get("id") or 0)
    uid = int(o.get("user_id") or 0)
    st_raw = str(o.get("status") or "")
    st = _st_label(st_raw)
    total = _fmt_money(int(o.get("total_kop") or 0))
    created = _fmt_dt(int(o.get("created_ts") or 0))

    text = (
        f"🧾 *Замовлення #{oid}*\n\n"
        f"Юзер: `{uid}`\n"
        f"Статус: *{st}* (`{st_raw}`)\n"
        f"Сума: *{total}*\n"
        f"Створено: _{created}_\n\n"
        f"_Статус змінюється менеджером. Автоматизацію (НП/CRM) додамо окремо._"
    )

    await _send_or_edit(
        bot,
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        reply_markup=_order_detail_kb(oid, page=page),
    )


async def _send_order_items(
    bot: Bot,
    chat_id: int,
    tenant_id: str,
    order_id: int,
    *,
    page: int,
    message_id: int | None,
) -> None:
    items = await TelegramShopOrdersRepo.list_order_items(int(order_id))
    items = items or []

    if not items:
        await _send_or_edit(
            bot,
            chat_id=chat_id,
            message_id=message_id,
            text=f"📦 *Товари в замовленні #{int(order_id)}*\n\nПоки що порожньо.",
            reply_markup=_order_items_kb(int(order_id), page=page),
        )
        return

    lines = [f"📦 *Товари в замовленні #{int(order_id)}*\n"]
    for it in items:
        name = str(it.get("name") or f"Товар #{it.get('product_id')}")
        qty = int(it.get("qty") or 0)
        price = _fmt_money(int(it.get("price_kop") or 0))
        lines.append(f"• *{name}* — {qty} шт × {price}")

    await _send_or_edit(
        bot,
        chat_id=chat_id,
        message_id=message_id,
        text="\n".join(lines),
        reply_markup=_order_items_kb(int(order_id), page=page),
    )


async def _set_order_status(
    bot: Bot,
    tenant_id: str,
    order_id: int,
    new_status: str,
) -> bool:
    new_status = (new_status or "").strip()
    if not new_status:
        return False

    # order must exist + grab user_id for notification
    o = await TelegramShopOrdersRepo.get_order(tenant_id, int(order_id))
    if not o:
        return False

    q = """
    UPDATE telegram_shop_orders
    SET status = $1
    WHERE tenant_id = $2 AND id = $3
    """
    await db_execute(q, new_status, tenant_id, int(order_id))

    # optional notify user
    user_id = int(o.get("user_id") or 0)
    if user_id > 0:
        try:
            st = _st_label(new_status)
            await bot.send_message(
                user_id,
                f"🧾 Статус вашого замовлення #{int(order_id)} оновлено: *{st}*",
                parse_mode="Markdown",
            )
        except Exception:
            pass

    return True


async def admin_orders_handle_update(*, tenant: dict, data: dict[str, Any], bot: Bot) -> bool:
    """
    Підключається з основного admin.py (tgadm:*).
    Повертає True якщо ми обробили апдейт.
    """
    cb = data.get("callback_query")
    if not cb:
        return False

    payload = str(cb.get("data") or "").strip()
    if not payload.startswith("tgadm:ord_") and not payload.startswith("tgadm:ord"):
        return False

    chat_id = int(cb["message"]["chat"]["id"])
    msg_id = int(cb["message"]["message_id"])
    tenant_id = str(tenant["id"])

    parts = payload.split(":")
    action = parts[1] if len(parts) > 1 else ""
    # формат:
    # tgadm:ord_menu:0
    # tgadm:ord_list:<page>
    # tgadm:ord_open:<oid>:<page>
    # tgadm:ord_items:<oid>:<page>
    # tgadm:ord_status_menu:<oid>:<page>
    # tgadm:ord_setst:<oid>:<status>:<page>

    if action == "ord_menu":
        await _send_admin_orders_menu(bot, chat_id, message_id=msg_id)
        return True

    if action == "ord_list":
        page = int(parts[2]) if len(parts) > 2 and str(parts[2]).lstrip("-").isdigit() else 0
        await _send_orders_list(bot, chat_id, tenant_id, page=page, message_id=msg_id)
        return True

    if action == "ord_open":
        oid = int(parts[2]) if len(parts) > 2 and str(parts[2]).isdigit() else 0
        page = int(parts[3]) if len(parts) > 3 and str(parts[3]).lstrip("-").isdigit() else 0
        if oid > 0:
            await _send_order_detail(bot, chat_id, tenant_id, oid, page=page, message_id=msg_id)
        return True

    if action == "ord_items":
        oid = int(parts[2]) if len(parts) > 2 and str(parts[2]).isdigit() else 0
        page = int(parts[3]) if len(parts) > 3 and str(parts[3]).lstrip("-").isdigit() else 0
        if oid > 0:
            await _send_order_items(bot, chat_id, tenant_id, oid, page=page, message_id=msg_id)
        return True

    if action == "ord_status_menu":
        oid = int(parts[2]) if len(parts) > 2 and str(parts[2]).isdigit() else 0
        page = int(parts[3]) if len(parts) > 3 and str(parts[3]).lstrip("-").isdigit() else 0
        if oid > 0:
            await _send_or_edit(
                bot,
                chat_id=chat_id,
                message_id=msg_id,
                text=f"✏️ *Статус замовлення #{oid}*\n\nОбери новий статус 👇",
                reply_markup=_order_status_menu_kb(oid, page=page),
            )
        return True

    if action == "ord_setst":
        oid = int(parts[2]) if len(parts) > 2 and str(parts[2]).isdigit() else 0
        new_st = str(parts[3]) if len(parts) > 3 else ""
        page = int(parts[4]) if len(parts) > 4 and str(parts[4]).lstrip("-").isdigit() else 0
        if oid > 0:
            await _set_order_status(bot, tenant_id, oid, new_st)
            await _send_order_detail(bot, chat_id, tenant_id, oid, page=page, message_id=msg_id)
        return True

    return False