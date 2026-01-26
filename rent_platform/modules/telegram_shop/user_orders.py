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


# =========================
# format helpers
# =========================
def _fmt_money(kop: int) -> str:
    kop = int(kop or 0)
    return f"{kop // 100}.{kop % 100:02d} грн"


def _fmt_dt(ts: int) -> str:
    ts = int(ts or 0)
    if ts <= 0:
        return "—"
    return _dt.datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M")


async def _send_or_edit_text(
    bot: Bot,
    *,
    chat_id: int,
    text: str,
    reply_markup: Any | None = None,
    message_id: int | None = None,
) -> None:
    """If message_id provided -> edit same message; else send new."""
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

    await bot.send_message(
        chat_id,
        text,
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )


# =========================
# list paging logic
# =========================
async def _load_orders_for_user(tenant_id: str, user_id: int) -> list[dict]:
    # беремо з запасом, щоб мати пагінацію без зміни репо
    orders = await TelegramShopOrdersRepo.list_orders(tenant_id, user_id, limit=200)
    return orders or []


async def _filter_orders_by_scope(
    tenant_id: str,
    user_id: int,
    orders: list[dict],
    *,
    scope: str,  # "active" | "arch"
) -> list[dict]:
    out: list[dict] = []
    want_arch = scope == "arch"

    # простий варіант: перевіряємо поштучно
    for o in orders:
        oid = int(o.get("id") or 0)
        if oid <= 0:
            continue
        is_arch = await TelegramShopOrdersArchiveRepo.is_archived(tenant_id, user_id, oid)
        if bool(is_arch) == bool(want_arch):
            out.append(o)

    return out


async def send_orders_list(
    bot: Bot,
    chat_id: int,
    tenant_id: str,
    user_id: int,
    *,
    page: int = 0,
    scope: str = "active",  # "active" | "arch"
    message_id: int | None = None,
) -> None:
    page = max(0, int(page))
    per_page = 10

    all_orders = await _load_orders_for_user(tenant_id, user_id)
    scoped = await _filter_orders_by_scope(tenant_id, user_id, all_orders, scope=scope)

    if not scoped:
        title = "🗃 *Архів замовлень*" if scope == "arch" else "🧾 *Історія замовлень*"
        empty = "Поки що порожньо." if scope == "active" else "Архів порожній."
        await _send_or_edit_text(
            bot,
            chat_id=chat_id,
            message_id=message_id,
            text=f"{title}\n\n{empty}",
            reply_markup=orders_list_kb([], page=0, has_prev=False, has_next=False, scope=scope),
        )
        return

    start = page * per_page
    chunk = scoped[start : start + per_page]
    has_prev = page > 0
    has_next = len(scoped) > start + per_page

    title = "🗃 *Архів замовлень*" if scope == "arch" else "🧾 *Історія замовлень*"
    lines = [title, ""]

    ids: list[int] = []
    for o in chunk:
        oid = int(o.get("id") or 0)
        if oid <= 0:
            continue
        ids.append(oid)

        st = status_label(str(o.get("status") or ""))
        total = _fmt_money(int(o.get("total_kop") or 0))
        created = _fmt_dt(int(o.get("created_ts") or 0))
        # коротко і читабельно
        lines.append(f"• *Замовлення #{oid}* — {st} — *{total}*")
        lines.append(f"  _{created}_")

    await _send_or_edit_text(
        bot,
        chat_id=chat_id,
        message_id=message_id,
        text="\n".join(lines),
        reply_markup=orders_list_kb(ids, page=page, has_prev=has_prev, has_next=has_next, scope=scope),
    )


async def send_order_detail(
    bot: Bot,
    chat_id: int,
    tenant_id: str,
    user_id: int,
    order_id: int,
    *,
    page: int = 0,
    scope: str = "active",
    message_id: int | None = None,
) -> None:
    o = await TelegramShopOrdersRepo.get_order(tenant_id, int(order_id))
    if not o:
        await _send_or_edit_text(
            bot,
            chat_id=chat_id,
            message_id=message_id,
            text="🧾 *Замовлення*\n\nЗамовлення не знайдено 😅",
            reply_markup=None,
        )
        return

    # security: show only own orders
    if int(o.get("user_id") or 0) != int(user_id):
        await _send_or_edit_text(
            bot,
            chat_id=chat_id,
            message_id=message_id,
            text="⛔ Це замовлення не належить вам.",
            reply_markup=None,
        )
        return

    oid = int(o.get("id") or 0)
    st = status_label(str(o.get("status") or ""))
    total = _fmt_money(int(o.get("total_kop") or 0))
    created = _fmt_dt(int(o.get("created_ts") or 0))

    # “В архів” — це саме архів (хованка), не статус
    is_arch = await TelegramShopOrdersArchiveRepo.is_archived(tenant_id, user_id, oid)

    # замість “(далі додамо…)” — короткий зрозумілий блок
    hint = (
        "ℹ️ *Як це працює:*\n"
        "• Статус змінює менеджер.\n"
        "• Коли зʼявиться інтеграція Нової Пошти — будемо підтягувати трек/події автоматично."
    )

    text = (
        f"🧾 *Замовлення #{oid}*\n\n"
        f"Статус: *{st}*\n"
        f"Сума: *{total}*\n"
        f"Створено: _{created}_\n\n"
        f"{hint}"
    )

    await _send_or_edit_text(
        bot,
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        reply_markup=order_detail_kb(oid, is_archived=bool(is_arch), page=page, scope=scope),
    )


async def send_order_items(
    bot: Bot,
    chat_id: int,
    tenant_id: str,
    user_id: int,
    order_id: int,
    *,
    page: int = 0,
    scope: str = "active",
    message_id: int | None = None,
) -> None:
    o = await TelegramShopOrdersRepo.get_order(tenant_id, int(order_id))
    if not o:
        await _send_or_edit_text(
            bot,
            chat_id=chat_id,
            message_id=message_id,
            text="📦 *Товари*\n\nЗамовлення не знайдено 😅",
            reply_markup=None,
        )
        return

    if int(o.get("user_id") or 0) != int(user_id):
        await _send_or_edit_text(
            bot,
            chat_id=chat_id,
            message_id=message_id,
            text="⛔ Це замовлення не належить вам.",
            reply_markup=None,
        )
        return

    items = await TelegramShopOrdersRepo.list_order_items(int(order_id))
    items = items or []

    if not items:
        await _send_or_edit_text(
            bot,
            chat_id=chat_id,
            message_id=message_id,
            text=f"📦 *Товари в замовленні #{int(order_id)}*\n\nПоки що порожньо.",
            reply_markup=order_items_kb(int(order_id), page=page, scope=scope),
        )
        return

    lines = [f"📦 *Товари в замовленні #{int(order_id)}*", ""]
    for it in items:
        name = str(it.get("name") or f"Товар #{it.get('product_id')}")
        qty = int(it.get("qty") or 0)
        price = _fmt_money(int(it.get("price_kop") or 0))
        lines.append(f"• *{name}* — {qty} шт × {price}")

    await _send_or_edit_text(
        bot,
        chat_id=chat_id,
        message_id=message_id,
        text="\n".join(lines),
        reply_markup=order_items_kb(int(order_id), page=page, scope=scope),
    )


# =========================
# callbacks
# =========================
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
      tgord:list:<page>:<scope>
      tgord:open:<order_id>:<page>:<scope>
      tgord:items:<order_id>:<page>:<scope>
      tgord:arch:<order_id>:<page>:<scope>      (toggle archive)
      tgord:toggle_scope:<page>:<scope>         (switch active<->arch)
    scope: "active" | "arch"
    """
    if not payload.startswith("tgord:"):
        return False

    parts = payload.split(":")
    action = parts[1] if len(parts) > 1 else ""
    a2 = parts[2] if len(parts) > 2 else "0"
    a3 = parts[3] if len(parts) > 3 else "0"
    a4 = parts[4] if len(parts) > 4 else "active"

    def _p_int(s: str, default: int = 0) -> int:
        return int(s) if str(s).isdigit() else default

    # list
    if action == "list":
        page = _p_int(a2, 0)
        scope = a3 if a3 in ("active", "arch") else "active"
        await send_orders_list(bot, chat_id, tenant_id, user_id, page=page, scope=scope, message_id=message_id)
        return True

    # open
    if action == "open":
        oid = _p_int(a2, 0)
        page = _p_int(a3, 0)
        scope = a4 if a4 in ("active", "arch") else "active"
        if oid > 0:
            await send_order_detail(bot, chat_id, tenant_id, user_id, oid, page=page, scope=scope, message_id=message_id)
        return True

    # items
    if action == "items":
        oid = _p_int(a2, 0)
        page = _p_int(a3, 0)
        scope = a4 if a4 in ("active", "arch") else "active"
        if oid > 0:
            await send_order_items(bot, chat_id, tenant_id, user_id, oid, page=page, scope=scope, message_id=message_id)
        return True

    # toggle archive
    if action == "arch":
        oid = _p_int(a2, 0)
        page = _p_int(a3, 0)
        scope = a4 if a4 in ("active", "arch") else "active"
        if oid > 0:
            await TelegramShopOrdersArchiveRepo.toggle(tenant_id, user_id, oid)
            # після перемикання лишаємо у detail (щоб юзер бачив що сталося)
            await send_order_detail(bot, chat_id, tenant_id, user_id, oid, page=page, scope=scope, message_id=message_id)
        return True

    # switch active<->arch
    if action == "toggle_scope":
        page = _p_int(a2, 0)
        scope = a3 if a3 in ("active", "arch") else "active"
        new_scope = "arch" if scope == "active" else "active"
        await send_orders_list(bot, chat_id, tenant_id, user_id, page=page, scope=new_scope, message_id=message_id)
        return True

    return True