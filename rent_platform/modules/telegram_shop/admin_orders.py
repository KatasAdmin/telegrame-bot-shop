# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as _dt
from typing import Any

from aiogram import Bot

from rent_platform.db.session import db_fetch_all, db_fetch_one, db_execute
from rent_platform.modules.telegram_shop.repo.orders import TelegramShopOrdersRepo
from rent_platform.modules.telegram_shop.repo.orders_archive import TelegramShopOrdersArchiveRepo

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


def _scope_norm(scope: str) -> str:
    scope = (scope or "").strip().lower()
    return scope if scope in ("active", "arch") else "active"


async def _count_orders(tenant_id: str, *, scope: str) -> int:
    scope = _scope_norm(scope)

    if scope == "arch":
        q = """
        SELECT COUNT(*) AS cnt
        FROM telegram_shop_orders o
        WHERE o.tenant_id = :tid
          AND EXISTS (
              SELECT 1
              FROM telegram_shop_orders_archive a
              WHERE a.tenant_id = o.tenant_id
                AND a.user_id = o.user_id
                AND a.order_id = o.id
          )
        """
        row = await db_fetch_one(q, {"tid": tenant_id}) or {}
        return int(row.get("cnt") or 0)

    q = """
    SELECT COUNT(*) AS cnt
    FROM telegram_shop_orders o
    WHERE o.tenant_id = :tid
      AND NOT EXISTS (
          SELECT 1
          FROM telegram_shop_orders_archive a
          WHERE a.tenant_id = o.tenant_id
            AND a.user_id = o.user_id
            AND a.order_id = o.id
      )
    """
    row = await db_fetch_one(q, {"tid": tenant_id}) or {}
    return int(row.get("cnt") or 0)


async def _list_orders_page(tenant_id: str, *, page: int, scope: str) -> list[dict]:
    page = max(0, int(page or 0))
    scope = _scope_norm(scope)

    if scope == "arch":
        q = """
        SELECT o.id, o.user_id, o.status, o.total_kop, o.created_ts
        FROM telegram_shop_orders o
        WHERE o.tenant_id = :tid
          AND EXISTS (
              SELECT 1
              FROM telegram_shop_orders_archive a
              WHERE a.tenant_id = o.tenant_id
                AND a.user_id = o.user_id
                AND a.order_id = o.id
          )
        ORDER BY o.id DESC
        LIMIT :lim OFFSET :off
        """
        return await db_fetch_all(q, {"tid": tenant_id, "lim": int(PAGE_SIZE), "off": int(page * PAGE_SIZE)}) or []

    q = """
    SELECT o.id, o.user_id, o.status, o.total_kop, o.created_ts
    FROM telegram_shop_orders o
    WHERE o.tenant_id = :tid
      AND NOT EXISTS (
          SELECT 1
          FROM telegram_shop_orders_archive a
          WHERE a.tenant_id = o.tenant_id
            AND a.user_id = o.user_id
            AND a.order_id = o.id
      )
    ORDER BY o.id DESC
    LIMIT :lim OFFSET :off
    """
    return await db_fetch_all(q, {"tid": tenant_id, "lim": int(PAGE_SIZE), "off": int(page * PAGE_SIZE)}) or []


def _orders_list_kb(order_ids: list[int], *, page: int, has_prev: bool, has_next: bool, scope: str) -> dict:
    scope = _scope_norm(scope)

    rows: list[list[tuple[str, str]]] = []
    for oid in order_ids:
        rows.append([(f"🧾 Замовлення #{oid}", f"tgadm:ord_open:{oid}:{page}:{scope}")])

    nav: list[tuple[str, str]] = [
        ("⬅️", f"tgadm:ord_list:{page-1}:{scope}") if has_prev else ("·", "tgadm:noop"),
        ("➡️", f"tgadm:ord_list:{page+1}:{scope}") if has_next else ("·", "tgadm:noop"),
    ]
    rows.append(nav)

    toggle_txt = "🗃 Архів" if scope == "active" else "🧾 Активні"
    rows.append([(toggle_txt, f"tgadm:ord_toggle_scope:{page}:{scope}")])

    rows.append([("⬅️ В адмін-меню", "tgadm:home:0")])
    return _kb(rows)


def _order_detail_kb(order_id: int, *, page: int, scope: str, is_archived: bool) -> dict:
    scope = _scope_norm(scope)

    arch_txt = "🧾 З архіву" if is_archived else "🗃 В архів"

    return _kb(
        [
            [("📦 Товари", f"tgadm:ord_items:{order_id}:{page}:{scope}")],
            [(arch_txt, f"tgadm:ord_arch:{order_id}:{page}:{scope}")],
            [("✏️ Змінити статус", f"tgadm:ord_status_menu:{order_id}:{page}:{scope}")],
            [("⬅️ Назад", f"tgadm:ord_list:{page}:{scope}")],
        ]
    )


def _order_items_kb(order_id: int, *, page: int, scope: str) -> dict:
    scope = _scope_norm(scope)
    return _kb([[("⬅️ Назад", f"tgadm:ord_open:{order_id}:{page}:{scope}")]])


def _order_status_menu_kb(order_id: int, *, page: int, scope: str) -> dict:
    scope = _scope_norm(scope)
    rows: list[list[tuple[str, str]]] = []
    for st, title in STATUSES:
        rows.append([(title, f"tgadm:ord_setst:{order_id}:{st}:{page}:{scope}")])
    rows.append([("⬅️ Назад", f"tgadm:ord_open:{order_id}:{page}:{scope}")])
    return _kb(rows)


async def _send_admin_orders_menu(bot: Bot, chat_id: int, *, message_id: int | None) -> None:
    kb = _kb(
        [
            [("🧾 Останні замовлення", "tgadm:ord_list:0:active")],
            [("🗃 Архів замовлень", "tgadm:ord_list:0:arch")],
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


async def _send_orders_list(
    bot: Bot,
    chat_id: int,
    tenant_id: str,
    *,
    page: int,
    scope: str,
    message_id: int | None,
) -> None:
    page = max(0, int(page or 0))
    scope = _scope_norm(scope)

    total = await _count_orders(tenant_id, scope=scope)
    rows = await _list_orders_page(tenant_id, page=page, scope=scope)

    title = "🧾 *Замовлення*" if scope == "active" else "🗃 *Архів замовлень*"

    if not rows:
        await _send_or_edit(
            bot,
            chat_id=chat_id,
            message_id=message_id,
            text=f"{title}\n\nПоки що порожньо.",
            reply_markup=_kb([[("⬅️ В адмін-меню", "tgadm:home:0")]]),
        )
        return

    order_ids: list[int] = [int(r["id"]) for r in rows if int(r.get("id") or 0) > 0]
    shown_from = page * PAGE_SIZE + 1
    shown_to = page * PAGE_SIZE + len(order_ids)

    lines = [f"{title} (показано {shown_from}-{shown_to} із {total})\n"]
    for r in rows:
        oid = int(r.get("id") or 0)
        uid = int(r.get("user_id") or 0)
        st = _st_label(str(r.get("status") or ""))
        total_uah = _fmt_money(int(r.get("total_kop") or 0))
        created = _fmt_dt(int(r.get("created_ts") or 0))
        lines.append(f"• #{oid} — `{uid}` — {st} — *{total_uah}* — _{created}_")

    has_prev = page > 0
    has_next = shown_to < total

    await _send_or_edit(
        bot,
        chat_id=chat_id,
        message_id=message_id,
        text="\n".join(lines),
        reply_markup=_orders_list_kb(order_ids, page=page, has_prev=has_prev, has_next=has_next, scope=scope),
    )


async def _send_order_detail(
    bot: Bot,
    chat_id: int,
    tenant_id: str,
    order_id: int,
    *,
    page: int,
    scope: str,
    message_id: int | None,
) -> None:
    scope = _scope_norm(scope)
    o = await TelegramShopOrdersRepo.get_order(tenant_id, int(order_id))
    if not o:
        await _send_or_edit(
            bot,
            chat_id=chat_id,
            message_id=message_id,
            text="🧾 *Замовлення*\n\nНе знайдено 😅",
            reply_markup=_kb([[("⬅️ Назад", f"tgadm:ord_list:{page}:{scope}")]]),
        )
        return

    oid = int(o.get("id") or 0)
    uid = int(o.get("user_id") or 0)
    st_raw = str(o.get("status") or "")
    st = _st_label(st_raw)
    total = _fmt_money(int(o.get("total_kop") or 0))
    created = _fmt_dt(int(o.get("created_ts") or 0))

    is_arch = await TelegramShopOrdersArchiveRepo.is_archived(tenant_id, uid, oid)

    text = (
        f"🧾 *Замовлення #{oid}*\n\n"
        f"Юзер: `{uid}`\n"
        f"Статус: *{st}* (`{st_raw}`)\n"
        f"Сума: *{total}*\n"
        f"Створено: _{created}_\n\n"
        f"_Статус змінює менеджер. Автоматизацію (НП/CRM) можна підʼєднати окремо._"
    )

    await _send_or_edit(
        bot,
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        reply_markup=_order_detail_kb(oid, page=page, scope=scope, is_archived=bool(is_arch)),
    )


async def _send_order_items(
    bot: Bot,
    chat_id: int,
    tenant_id: str,
    order_id: int,
    *,
    page: int,
    scope: str,
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
            reply_markup=_order_items_kb(int(order_id), page=page, scope=scope),
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
        reply_markup=_order_items_kb(int(order_id), page=page, scope=scope),
    )


async def _set_order_status(bot: Bot, tenant_id: str, order_id: int, new_status: str) -> bool:
    new_status = (new_status or "").strip()
    if not new_status:
        return False

    o = await TelegramShopOrdersRepo.get_order(tenant_id, int(order_id))
    if not o:
        return False

    q = """
    UPDATE telegram_shop_orders
    SET status = :st
    WHERE tenant_id = :tid AND id = :oid
    """
    await db_execute(q, {"st": new_status, "tid": tenant_id, "oid": int(order_id)})

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
    cb = data.get("callback_query")
    if not cb:
        return False

    payload = str(cb.get("data") or "").strip()
    if not payload.startswith("tgadm:ord"):
        return False

    chat_id = int(cb["message"]["chat"]["id"])
    msg_id = int(cb["message"]["message_id"])
    tenant_id = str(tenant["id"])

    parts = payload.split(":")
    action = parts[1] if len(parts) > 1 else ""

    # tgadm:ord_menu:0
    if action == "ord_menu":
        await _send_admin_orders_menu(bot, chat_id, message_id=msg_id)
        return True

    # tgadm:ord_list:<page>:<scope>
    if action == "ord_list":
        page = int(parts[2]) if len(parts) > 2 and str(parts[2]).lstrip("-").isdigit() else 0
        scope = str(parts[3]) if len(parts) > 3 else "active"
        await _send_orders_list(bot, chat_id, tenant_id, page=page, scope=scope, message_id=msg_id)
        return True

    # tgadm:ord_toggle_scope:<page>:<scope>
    if action == "ord_toggle_scope":
        page = int(parts[2]) if len(parts) > 2 and str(parts[2]).lstrip("-").isdigit() else 0
        scope = str(parts[3]) if len(parts) > 3 else "active"
        new_scope = "arch" if _scope_norm(scope) == "active" else "active"
        await _send_orders_list(bot, chat_id, tenant_id, page=page, scope=new_scope, message_id=msg_id)
        return True

    # tgadm:ord_open:<oid>:<page>:<scope>
    if action == "ord_open":
        oid = int(parts[2]) if len(parts) > 2 and str(parts[2]).isdigit() else 0
        page = int(parts[3]) if len(parts) > 3 and str(parts[3]).lstrip("-").isdigit() else 0
        scope = str(parts[4]) if len(parts) > 4 else "active"
        if oid > 0:
            await _send_order_detail(bot, chat_id, tenant_id, oid, page=page, scope=scope, message_id=msg_id)
        return True

    # tgadm:ord_items:<oid>:<page>:<scope>
    if action == "ord_items":
        oid = int(parts[2]) if len(parts) > 2 and str(parts[2]).isdigit() else 0
        page = int(parts[3]) if len(parts) > 3 and str(parts[3]).lstrip("-").isdigit() else 0
        scope = str(parts[4]) if len(parts) > 4 else "active"
        if oid > 0:
            await _send_order_items(bot, chat_id, tenant_id, oid, page=page, scope=scope, message_id=msg_id)
        return True

    # tgadm:ord_arch:<oid>:<page>:<scope>  (toggle archive)
    if action == "ord_arch":
        oid = int(parts[2]) if len(parts) > 2 and str(parts[2]).isdigit() else 0
        page = int(parts[3]) if len(parts) > 3 and str(parts[3]).lstrip("-").isdigit() else 0
        scope = str(parts[4]) if len(parts) > 4 else "active"
        if oid > 0:
            o = await TelegramShopOrdersRepo.get_order(tenant_id, int(oid)) or {}
            uid = int(o.get("user_id") or 0)
            if uid > 0:
                await TelegramShopOrdersArchiveRepo.toggle(tenant_id, uid, int(oid))
            await _send_order_detail(bot, chat_id, tenant_id, oid, page=page, scope=scope, message_id=msg_id)
        return True

    # tgadm:ord_status_menu:<oid>:<page>:<scope>
    if action == "ord_status_menu":
        oid = int(parts[2]) if len(parts) > 2 and str(parts[2]).isdigit() else 0
        page = int(parts[3]) if len(parts) > 3 and str(parts[3]).lstrip("-").isdigit() else 0
        scope = str(parts[4]) if len(parts) > 4 else "active"
        if oid > 0:
            await _send_or_edit(
                bot,
                chat_id=chat_id,
                message_id=msg_id,
                text=f"✏️ *Статус замовлення #{oid}*\n\nОбери новий статус 👇",
                reply_markup=_order_status_menu_kb(oid, page=page, scope=scope),
            )
        return True

    # tgadm:ord_setst:<oid>:<status>:<page>:<scope>
    if action == "ord_setst":
        oid = int(parts[2]) if len(parts) > 2 and str(parts[2]).isdigit() else 0
        new_st = str(parts[3]) if len(parts) > 3 else ""
        page = int(parts[4]) if len(parts) > 4 and str(parts[4]).lstrip("-").isdigit() else 0
        scope = str(parts[5]) if len(parts) > 5 else "active"
        if oid > 0:
            await _set_order_status(bot, tenant_id, oid, new_st)
            await _send_order_detail(bot, chat_id, tenant_id, oid, page=page, scope=scope, message_id=msg_id)
        return True

    return True