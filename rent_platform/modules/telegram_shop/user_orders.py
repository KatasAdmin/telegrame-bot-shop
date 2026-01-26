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


PAGE_SIZE = 10
HISTORY_FETCH_LIMIT = 300  # скільки останніх тягнемо з БД під пагінацію


def _fmt_money(kop: int) -> str:
    kop = int(kop or 0)
    return f"{kop // 100}.{kop % 100:02d} грн"


def _fmt_dt(ts: int) -> str:
    ts = int(ts or 0)
    if ts <= 0:
        return "—"
    return _dt.datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M")


async def _send_or_edit(
    bot: Bot,
    chat_id: int,
    text: str,
    *,
    parse_mode: str | None = "Markdown",
    reply_markup: Any | None = None,
    message_id: int | None = None,
) -> None:
    """
    Якщо передали message_id — намагаємось редагувати те саме повідомлення.
    Якщо редагування неможливе — просто send_message.
    """
    if message_id:
        try:
            await bot.edit_message_text(
                text,
                chat_id=chat_id,
                message_id=int(message_id),
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
            return
        except Exception:
            pass

    await bot.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup)


async def _load_orders_filtered(
    tenant_id: str,
    user_id: int,
    *,
    archived: bool,
) -> list[dict]:
    """
    Тягнемо останні N замовлень і фільтруємо по archive-мітці.
    (N невелике, тому N+1 запити на is_archived не страшні)
    """
    orders = await TelegramShopOrdersRepo.list_orders(tenant_id, user_id, limit=HISTORY_FETCH_LIMIT)
    orders = orders or []

    out: list[dict] = []
    for o in orders:
        oid = int(o.get("id") or 0)
        if oid <= 0:
            continue
        is_arch = await TelegramShopOrdersArchiveRepo.is_archived(tenant_id, user_id, oid)
        if bool(is_arch) == bool(archived):
            out.append(o)
    return out


async def send_orders_list(
    bot: Bot,
    chat_id: int,
    tenant_id: str,
    user_id: int,
    *,
    page: int = 0,
    archived: bool = False,
    message_id: int | None = None,
) -> None:
    page = max(int(page or 0), 0)

    orders = await _load_orders_filtered(tenant_id, user_id, archived=archived)

    title = "🗄 *Архів замовлень*" if archived else "🧾 *Історія замовлень*"

    if not orders:
        empty_txt = (
            f"{title}\n\nПоки що порожньо."
            if not archived
            else f"{title}\n\nАрхів порожній."
        )
        await _send_or_edit(
            bot,
            chat_id,
            empty_txt,
            message_id=message_id,
            reply_markup=orders_list_kb(
                order_ids=[],
                page=0,
                has_prev=False,
                has_next=False,
                archived=archived,
            ),
        )
        return

    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    chunk = orders[start:end]

    has_prev = page > 0
    has_next = end < len(orders)

    lines = [f"{title}\n"]
    ids: list[int] = []

    for o in chunk:
        oid = int(o.get("id") or 0)
        if oid <= 0:
            continue
        ids.append(oid)

        st = status_label(str(o.get("status") or ""))
        total = _fmt_money(int(o.get("total_kop") or 0))
        created = _fmt_dt(int(o.get("created_ts") or 0))
        lines.append(f"• #{oid} — {st} — *{total}* — _{created}_")

    # індикатор сторінки
    total_pages = (len(orders) + PAGE_SIZE - 1) // PAGE_SIZE
    lines.append(f"\n_Сторінка {page + 1}/{max(total_pages, 1)}_")

    await _send_or_edit(
        bot,
        chat_id,
        "\n".join(lines),
        message_id=message_id,
        reply_markup=orders_list_kb(
            order_ids=ids,
            page=page,
            has_prev=has_prev,
            has_next=has_next,
            archived=archived,
        ),
    )


async def send_order_detail(
    bot: Bot,
    chat_id: int,
    tenant_id: str,
    user_id: int,
    order_id: int,
    *,
    message_id: int | None = None,
) -> None:
    o = await TelegramShopOrdersRepo.get_order(tenant_id, int(order_id))
    if not o:
        await _send_or_edit(bot, chat_id, "Замовлення не знайдено 😅", message_id=message_id)
        return

    if int(o.get("user_id") or 0) != int(user_id):
        await _send_or_edit(bot, chat_id, "⛔ Це замовлення не належить вам.", message_id=message_id)
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
        f"ℹ️ Статус оновлює менеджер. Коли буде відправка/ТТН — ми покажемо в цьому замовленні.\n"
    )

    await _send_or_edit(
        bot,
        chat_id,
        text,
        message_id=message_id,
        reply_markup=order_detail_kb(oid, is_archived=bool(is_arch)),
    )


async def send_order_items(
    bot: Bot,
    chat_id: int,
    tenant_id: str,
    user_id: int,
    order_id: int,
    *,
    message_id: int | None = None,
) -> None:
    o = await TelegramShopOrdersRepo.get_order(tenant_id, int(order_id))
    if not o:
        await _send_or_edit(bot, chat_id, "Замовлення не знайдено 😅", message_id=message_id)
        return

    if int(o.get("user_id") or 0) != int(user_id):
        await _send_or_edit(bot, chat_id, "⛔ Це замовлення не належить вам.", message_id=message_id)
        return

    items = await TelegramShopOrdersRepo.list_order_items(int(order_id))
    items = items or []

    if not items:
        await _send_or_edit(
            bot,
            chat_id,
            f"📦 *Товари в замовленні #{int(order_id)}*\n\nПоки що порожньо.",
            message_id=message_id,
            reply_markup=order_items_kb(int(order_id)),
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
        chat_id,
        "\n".join(lines),
        message_id=message_id,
        reply_markup=order_items_kb(int(order_id)),
    )


async def handle_orders_callback(
    *,
    bot: Bot,
    tenant_id: str,
    user_id: int,
    chat_id: int,
    payload: str,
    message_id: int | None = None,
) -> bool:
    """
    callback_data:
      tgord:list:<page>            # історія
      tgord:alist:<page>           # архів
      tgord:open:<order_id>
      tgord:items:<order_id>
      tgord:arch:<order_id>        # toggle archive (hide/unhide)
    """
    if not payload.startswith("tgord:"):
        return False

    parts = payload.split(":")
    action = parts[1] if len(parts) > 1 else ""
    raw = parts[2] if len(parts) > 2 else "0"

    if action in ("list", "alist"):
        page = int(raw) if raw.isdigit() else 0
        await send_orders_list(
            bot,
            chat_id,
            tenant_id,
            user_id,
            page=page,
            archived=(action == "alist"),
            message_id=message_id,
        )
        return True

    if action == "open":
        oid = int(raw) if raw.isdigit() else 0
        if oid > 0:
            await send_order_detail(bot, chat_id, tenant_id, user_id, oid, message_id=message_id)
        return True

    if action == "items":
        oid = int(raw) if raw.isdigit() else 0
        if oid > 0:
            await send_order_items(bot, chat_id, tenant_id, user_id, oid, message_id=message_id)
        return True

    if action == "arch":
        oid = int(raw) if raw.isdigit() else 0
        if oid > 0:
            await TelegramShopOrdersArchiveRepo.toggle(tenant_id, user_id, oid)
            await send_order_detail(bot, chat_id, tenant_id, user_id, oid, message_id=message_id)
        return True

    return True