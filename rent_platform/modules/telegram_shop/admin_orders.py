# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as _dt
import io
from typing import Any

from aiogram import Bot
from aiogram.types import BufferedInputFile

from rent_platform.db.session import db_fetch_all, db_fetch_one, db_execute
from rent_platform.modules.telegram_shop.repo.orders import TelegramShopOrdersRepo
from rent_platform.modules.telegram_shop.repo.orders_admin_archive import TelegramShopOrdersAdminArchiveRepo

try:
    from rent_platform.modules.telegram_shop.ui.orders_status import status_label  # type: ignore
except Exception:  # pragma: no cover
    status_label = None  # type: ignore


PAGE_SIZE = 10

# вкладки адміна
TAB_NEW = "new"
TAB_WORK = "work"
TAB_DONE = "done"
TAB_ARCH = "arch"

# групи статусів
NEW_STATUSES = ("new",)
WORK_STATUSES = ("accepted", "packed", "shipped")
DONE_STATUSES = ("delivered", "not_received", "returned", "cancelled")


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


def _tab_norm(tab: str) -> str:
    tab = (tab or "").strip().lower()
    return tab if tab in (TAB_NEW, TAB_WORK, TAB_DONE, TAB_ARCH) else TAB_NEW


def _tab_title(tab: str) -> str:
    tab = _tab_norm(tab)
    if tab == TAB_NEW:
        return "🆕 *Нові замовлення*"
    if tab == TAB_WORK:
        return "⚙️ *В роботі*"
    if tab == TAB_DONE:
        return "✅ *Завершені*"
    return "🗃 *Архів адміна*"


def _statuses_for_tab(tab: str) -> tuple[str, ...] | None:
    tab = _tab_norm(tab)
    if tab == TAB_NEW:
        return NEW_STATUSES
    if tab == TAB_WORK:
        return WORK_STATUSES
    if tab == TAB_DONE:
        return DONE_STATUSES
    return None  # архів не по статусу


async def _count_orders(tenant_id: str, *, tab: str) -> int:
    tab = _tab_norm(tab)

    if tab == TAB_ARCH:
        q = """
        SELECT COUNT(*) AS cnt
        FROM telegram_shop_orders o
        WHERE o.tenant_id = :tid
          AND EXISTS (
              SELECT 1
              FROM telegram_shop_orders_admin_archive a
              WHERE a.tenant_id = o.tenant_id
                AND a.order_id = o.id
          )
        """
        row = await db_fetch_one(q, {"tid": tenant_id}) or {}
        return int(row.get("cnt") or 0)

    statuses = _statuses_for_tab(tab) or ()
    q = """
    SELECT COUNT(*) AS cnt
    FROM telegram_shop_orders o
    WHERE o.tenant_id = :tid
      AND o.status = ANY(:sts)
      AND NOT EXISTS (
          SELECT 1
          FROM telegram_shop_orders_admin_archive a
          WHERE a.tenant_id = o.tenant_id
            AND a.order_id = o.id
      )
    """
    row = await db_fetch_one(q, {"tid": tenant_id, "sts": list(statuses)}) or {}
    return int(row.get("cnt") or 0)


async def _list_orders_page(tenant_id: str, *, page: int, tab: str) -> list[dict]:
    page = max(0, int(page or 0))
    tab = _tab_norm(tab)

    if tab == TAB_ARCH:
        q = """
        SELECT o.id, o.user_id, o.status, o.total_kop, o.created_ts
        FROM telegram_shop_orders o
        WHERE o.tenant_id = :tid
          AND EXISTS (
              SELECT 1
              FROM telegram_shop_orders_admin_archive a
              WHERE a.tenant_id = o.tenant_id
                AND a.order_id = o.id
          )
        ORDER BY o.id DESC
        LIMIT :lim OFFSET :off
        """
        return await db_fetch_all(q, {"tid": tenant_id, "lim": int(PAGE_SIZE), "off": int(page * PAGE_SIZE)}) or []

    statuses = _statuses_for_tab(tab) or ()
    q = """
    SELECT o.id, o.user_id, o.status, o.total_kop, o.created_ts
    FROM telegram_shop_orders o
    WHERE o.tenant_id = :tid
      AND o.status = ANY(:sts)
      AND NOT EXISTS (
          SELECT 1
          FROM telegram_shop_orders_admin_archive a
          WHERE a.tenant_id = o.tenant_id
            AND a.order_id = o.id
      )
    ORDER BY o.id DESC
    LIMIT :lim OFFSET :off
    """
    return await db_fetch_all(
        q,
        {"tid": tenant_id, "sts": list(statuses), "lim": int(PAGE_SIZE), "off": int(page * PAGE_SIZE)},
    ) or []


def _tabs_row(active_tab: str, page: int) -> list[tuple[str, str]]:
    t = _tab_norm(active_tab)

    def _btn(title: str, tab: str) -> tuple[str, str]:
        prefix = "• " if t == tab else ""
        return (f"{prefix}{title}", f"tgadm:ord_tab:{tab}:{page}")

    return [
        _btn("🆕 Нові", TAB_NEW),
        _btn("⚙️ В роботі", TAB_WORK),
        _btn("✅ Завершені", TAB_DONE),
        _btn("🗃 Архів", TAB_ARCH),
    ]


def _orders_list_kb(order_ids: list[int], *, page: int, has_prev: bool, has_next: bool, tab: str) -> dict:
    tab = _tab_norm(tab)
    rows: list[list[tuple[str, str]]] = []

    # вкладки
    rows.append(_tabs_row(tab, page))

    # експорт тільки для "Нові"
    if tab == TAB_NEW:
        rows.append([("📦 Скачати накладну (Нові)", f"tgadm:ord_export:new:{page}")])

    # замовлення
    for oid in order_ids:
        rows.append([(f"🧾 Замовлення #{oid}", f"tgadm:ord_open:{oid}:{page}:{tab}")])

    # навігація
    nav: list[tuple[str, str]] = [
        ("⬅️", f"tgadm:ord_tab:{tab}:{page-1}") if has_prev else ("·", "tgadm:noop"),
        ("➡️", f"tgadm:ord_tab:{tab}:{page+1}") if has_next else ("·", "tgadm:noop"),
    ]
    rows.append(nav)

    rows.append([("⬅️ В адмін-меню", "tgadm:home:0")])
    return _kb(rows)


def _order_detail_kb(order_id: int, *, page: int, tab: str, is_archived: bool) -> dict:
    tab = _tab_norm(tab)
    arch_txt = "🧾 З архіву" if is_archived else "🗃 В архів"
    return _kb(
        [
            [("📦 Товари", f"tgadm:ord_items:{order_id}:{page}:{tab}")],
            [(arch_txt, f"tgadm:ord_arch:{order_id}:{page}:{tab}")],
            [("✏️ Змінити статус", f"tgadm:ord_status_menu:{order_id}:{page}:{tab}")],
            [("⬅️ Назад", f"tgadm:ord_tab:{tab}:{page}")],
        ]
    )


def _order_items_kb(order_id: int, *, page: int, tab: str) -> dict:
    tab = _tab_norm(tab)
    return _kb([[("⬅️ Назад", f"tgadm:ord_open:{order_id}:{page}:{tab}")]])


def _order_status_menu_kb(order_id: int, *, page: int, tab: str) -> dict:
    tab = _tab_norm(tab)
    rows: list[list[tuple[str, str]]] = []
    for st, title in STATUSES:
        rows.append([(title, f"tgadm:ord_setst:{order_id}:{st}:{page}:{tab}")])
    rows.append([("⬅️ Назад", f"tgadm:ord_open:{order_id}:{page}:{tab}")])
    return _kb(rows)


async def _send_admin_orders_menu(bot: Bot, chat_id: int, *, message_id: int | None) -> None:
    kb = _kb(
        [
            [("🧾 Замовлення", f"tgadm:ord_tab:{TAB_NEW}:0")],
            [("⬅️ В адмін-меню", "tgadm:home:0")],
        ]
    )
    await _send_or_edit(
        bot,
        chat_id=chat_id,
        message_id=message_id,
        text="🧾 *Адмін — Замовлення*\n\nОбери вкладку 👇",
        reply_markup=kb,
    )


async def _send_orders_list(
    bot: Bot,
    chat_id: int,
    tenant_id: str,
    *,
    page: int,
    tab: str,
    message_id: int | None,
) -> None:
    page = max(0, int(page or 0))
    tab = _tab_norm(tab)

    total = await _count_orders(tenant_id, tab=tab)
    rows = await _list_orders_page(tenant_id, page=page, tab=tab)

    title = _tab_title(tab)

    if not rows:
        await _send_or_edit(
            bot,
            chat_id=chat_id,
            message_id=message_id,
            text=f"{title}\n\nПоки що порожньо.",
            reply_markup=_kb([_tabs_row(tab, page), [("⬅️ В адмін-меню", "tgadm:home:0")]]),
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
        reply_markup=_orders_list_kb(order_ids, page=page, has_prev=has_prev, has_next=has_next, tab=tab),
    )


async def _send_order_detail(
    bot: Bot,
    chat_id: int,
    tenant_id: str,
    order_id: int,
    *,
    page: int,
    tab: str,
    message_id: int | None,
) -> None:
    tab = _tab_norm(tab)
    o = await TelegramShopOrdersRepo.get_order(tenant_id, int(order_id))
    if not o:
        await _send_or_edit(
            bot,
            chat_id=chat_id,
            message_id=message_id,
            text="🧾 *Замовлення*\n\nНе знайдено 😅",
            reply_markup=_kb([[("⬅️ Назад", f"tgadm:ord_tab:{tab}:{page}")]]),
        )
        return

    oid = int(o.get("id") or 0)
    uid = int(o.get("user_id") or 0)
    st_raw = str(o.get("status") or "")
    st = _st_label(st_raw)
    total = _fmt_money(int(o.get("total_kop") or 0))
    created = _fmt_dt(int(o.get("created_ts") or 0))

    is_arch = await TelegramShopOrdersAdminArchiveRepo.is_archived(tenant_id, oid)

    text = (
        f"🧾 *Замовлення #{oid}*\n\n"
        f"Юзер: `{uid}`\n"
        f"Статус: *{st}* (`{st_raw}`)\n"
        f"Сума: *{total}*\n"
        f"Створено: _{created}_\n\n"
        f"ℹ️ Далі додамо НП: ключ → створення ТТН → автоподії → авто-статуси."
    )

    await _send_or_edit(
        bot,
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        reply_markup=_order_detail_kb(oid, page=page, tab=tab, is_archived=bool(is_arch)),
    )


async def _send_order_items(
    bot: Bot,
    chat_id: int,
    tenant_id: str,
    order_id: int,
    *,
    page: int,
    tab: str,
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
            reply_markup=_order_items_kb(int(order_id), page=page, tab=tab),
        )
        return

    lines = [f"📦 *Товари в замовленні #{int(order_id)}*\n"]
    for it in items:
        name = str(it.get("name") or f"Товар #{it.get('product_id')}")
        sku = str(it.get("sku") or "").strip()
        qty = int(it.get("qty") or 0)
        price = _fmt_money(int(it.get("price_kop") or 0))
        sku_part = f" (`{sku}`)" if sku else ""
        lines.append(f"• *{name}*{sku_part} — {qty} шт × {price}")

    await _send_or_edit(
        bot,
        chat_id=chat_id,
        message_id=message_id,
        text="\n".join(lines),
        reply_markup=_order_items_kb(int(order_id), page=page, tab=tab),
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


async def _export_new_orders_picklist(bot: Bot, chat_id: int, tenant_id: str) -> None:
    # беремо всі нові, які не в адмін-архіві
    q = """
    SELECT o.id, o.user_id, o.created_ts
    FROM telegram_shop_orders o
    WHERE o.tenant_id = :tid
      AND o.status = 'new'
      AND NOT EXISTS (
          SELECT 1 FROM telegram_shop_orders_admin_archive a
          WHERE a.tenant_id = o.tenant_id AND a.order_id = o.id
      )
    ORDER BY o.id ASC
    LIMIT 200
    """
    orders = await db_fetch_all(q, {"tid": tenant_id}) or []
    if not orders:
        await bot.send_message(chat_id, "🆕 Нових замовлень немає.")
        return

    # TSV як “накладна”
    out = io.StringIO()
    out.write("order_id\tuser_id\tcreated\tsku\tname\tqty\tprice_uah\n")

    for o in orders:
        oid = int(o.get("id") or 0)
        uid = int(o.get("user_id") or 0)
        created = _fmt_dt(int(o.get("created_ts") or 0))
        items = await TelegramShopOrdersRepo.list_order_items(oid)
        for it in items or []:
            sku = str(it.get("sku") or "").strip()
            name = str(it.get("name") or "")
            qty = int(it.get("qty") or 0)
            price = _fmt_money(int(it.get("price_kop") or 0))
            out.write(f"{oid}\t{uid}\t{created}\t{sku}\t{name}\t{qty}\t{price}\n")

    data = out.getvalue().encode("utf-8")
    file = BufferedInputFile(data, filename="new_orders_picklist.tsv")
    await bot.send_document(chat_id, file, caption="📦 Накладна (pick-list) по *Нових* замовленнях", parse_mode="Markdown")


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

    # tgadm:ord_tab:<tab>:<page>
    if action == "ord_tab":
        tab = str(parts[2]) if len(parts) > 2 else TAB_NEW
        page = int(parts[3]) if len(parts) > 3 and str(parts[3]).lstrip("-").isdigit() else 0
        await _send_orders_list(bot, chat_id, tenant_id, page=page, tab=tab, message_id=msg_id)
        return True

    # tgadm:ord_export:new:<page>
    if action == "ord_export":
        kind = str(parts[2]) if len(parts) > 2 else "new"
        if kind == "new":
            await _export_new_orders_picklist(bot, chat_id, tenant_id)
        return True

    # tgadm:ord_open:<oid>:<page>:<tab>
    if action == "ord_open":
        oid = int(parts[2]) if len(parts) > 2 and str(parts[2]).isdigit() else 0
        page = int(parts[3]) if len(parts) > 3 and str(parts[3]).lstrip("-").isdigit() else 0
        tab = str(parts[4]) if len(parts) > 4 else TAB_NEW
        if oid > 0:
            await _send_order_detail(bot, chat_id, tenant_id, oid, page=page, tab=tab, message_id=msg_id)
        return True

    # tgadm:ord_items:<oid>:<page>:<tab>
    if action == "ord_items":
        oid = int(parts[2]) if len(parts) > 2 and str(parts[2]).isdigit() else 0
        page = int(parts[3]) if len(parts) > 3 and str(parts[3]).lstrip("-").isdigit() else 0
        tab = str(parts[4]) if len(parts) > 4 else TAB_NEW
        if oid > 0:
            await _send_order_items(bot, chat_id, tenant_id, oid, page=page, tab=tab, message_id=msg_id)
        return True

    # tgadm:ord_arch:<oid>:<page>:<tab>
    if action == "ord_arch":
        oid = int(parts[2]) if len(parts) > 2 and str(parts[2]).isdigit() else 0
        page = int(parts[3]) if len(parts) > 3 and str(parts[3]).lstrip("-").isdigit() else 0
        tab = str(parts[4]) if len(parts) > 4 else TAB_NEW
        if oid > 0:
            await TelegramShopOrdersAdminArchiveRepo.toggle(tenant_id, int(oid))
            await _send_order_detail(bot, chat_id, tenant_id, oid, page=page, tab=tab, message_id=msg_id)
        return True

    # tgadm:ord_status_menu:<oid>:<page>:<tab>
    if action == "ord_status_menu":
        oid = int(parts[2]) if len(parts) > 2 and str(parts[2]).isdigit() else 0
        page = int(parts[3]) if len(parts) > 3 and str(parts[3]).lstrip("-").isdigit() else 0
        tab = str(parts[4]) if len(parts) > 4 else TAB_NEW
        if oid > 0:
            await _send_or_edit(
                bot,
                chat_id=chat_id,
                message_id=msg_id,
                text=f"✏️ *Статус замовлення #{oid}*\n\nОбери новий статус 👇",
                reply_markup=_order_status_menu_kb(oid, page=page, tab=tab),
            )
        return True

    # tgadm:ord_setst:<oid>:<status>:<page>:<tab>
    if action == "ord_setst":
        oid = int(parts[2]) if len(parts) > 2 and str(parts[2]).isdigit() else 0
        new_st = str(parts[3]) if len(parts) > 3 else ""
        page = int(parts[4]) if len(parts) > 4 and str(parts[4]).lstrip("-").isdigit() else 0
        tab = str(parts[5]) if len(parts) > 5 else TAB_NEW
        if oid > 0:
            await _set_order_status(bot, tenant_id, oid, new_st)
            await _send_order_detail(bot, chat_id, tenant_id, oid, page=page, tab=tab, message_id=msg_id)
        return True

    return True


# --- public wrappers (for reply-keyboard entry points) ---

async def admin_orders_send_menu(bot: Bot, chat_id: int) -> None:
    await _send_admin_orders_menu(bot, chat_id, message_id=None)


async def admin_orders_send_list(bot: Bot, chat_id: int, tenant_id: str, *, scope: str) -> None:
    # scope: "new" | "work" | "done" | "arch" | "active"
    scope = (scope or "").strip().lower()

    if scope in ("arch", "archive"):
        tab = TAB_ARCH
    elif scope in ("work", "in_work"):
        tab = TAB_WORK
    elif scope in ("done", "finished"):
        tab = TAB_DONE
    else:
        # "new" або "active" -> відкриваємо нові
        tab = TAB_NEW

    await _send_orders_list(
        bot,
        chat_id,
        tenant_id,
        page=0,
        tab=tab,
        message_id=None,
    )