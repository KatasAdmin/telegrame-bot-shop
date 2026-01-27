from __future__ import annotations

import datetime as _dt
from typing import Any

from aiogram import Bot
from aiogram.types import InputMediaPhoto

from rent_platform.modules.telegram_shop.repo.orders import TelegramShopOrdersRepo
from rent_platform.modules.telegram_shop.repo.orders_archive import TelegramShopOrdersArchiveRepo
from rent_platform.modules.telegram_shop.repo.products import ProductsRepo
from rent_platform.modules.telegram_shop.ui.inline_orders_kb import (
    orders_list_kb,
    order_detail_kb,
    order_items_list_kb,
    order_item_back_kb,
    order_history_back_kb,
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

    await bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=reply_markup)


async def _send_or_edit_product_card(
    bot: Bot,
    *,
    chat_id: int,
    message_id: int | None,
    file_id: str | None,
    text: str,
    reply_markup: Any | None,
) -> None:
    """
    Показ картки товару "як в каталозі":
    - якщо є фото і можемо — робимо edit_message_media
    - інакше edit text або send
    """
    if message_id and file_id:
        try:
            media = InputMediaPhoto(media=file_id, caption=text, parse_mode="Markdown")
            await bot.edit_message_media(
                media=media,
                chat_id=chat_id,
                message_id=int(message_id),
                reply_markup=reply_markup,
            )
            return
        except Exception:
            pass

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

    # fallback send
    if file_id:
        await bot.send_photo(chat_id, photo=file_id, caption=text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=reply_markup)


# =========================
# list logic
# =========================
async def _load_orders_for_user(tenant_id: str, user_id: int) -> list[dict]:
    # беремо з запасом, щоб мати пагінацію без зміни репо
    return await TelegramShopOrdersRepo.list_orders(tenant_id, user_id, limit=200) or []


async def _split_orders_by_archive(
    tenant_id: str,
    user_id: int,
    orders: list[dict],
) -> tuple[list[dict], list[dict]]:
    """
    Повертає (active, arch) з ОДНИМ проходом (щоб не робити зайві запити).
    """
    active: list[dict] = []
    arch: list[dict] = []

    for o in orders or []:
        oid = int(o.get("id") or 0)
        if oid <= 0:
            continue
        is_arch = await TelegramShopOrdersArchiveRepo.is_archived(tenant_id, user_id, oid)
        (arch if is_arch else active).append(o)

    return active, arch


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
    scope = scope if scope in ("active", "arch") else "active"

    all_orders = await _load_orders_for_user(tenant_id, user_id)
    active, arch = await _split_orders_by_archive(tenant_id, user_id, all_orders)

    scoped = arch if scope == "arch" else active

    total_all = len(all_orders)
    total_active = len(active)
    total_arch = len(arch)

    title = "🗃 *Архів замовлень*" if scope == "arch" else "🧾 *Історія замовлень*"

    if not scoped:
        empty = "Архів порожній." if scope == "arch" else "Поки що порожньо."
        text = (
            f"{title}\n\n"
            f"Всього: *{total_all}* • Активні: *{total_active}* • Архів: *{total_arch}*\n\n"
            f"{empty}"
        )
        await _send_or_edit_text(
            bot,
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=orders_list_kb([], page=0, has_prev=False, has_next=False, scope=scope),
        )
        return

    start = page * per_page
    chunk = scoped[start : start + per_page]
    has_prev = page > 0
    has_next = len(scoped) > start + per_page

    # Текст зверху: без "замовлення 5", просто статистика
    text = (
        f"{title}\n\n"
        f"Всього: *{total_all}* • Активні: *{total_active}* • Архів: *{total_arch}*\n"
        "Обери замовлення 👇"
    )

    await _send_or_edit_text(
        bot,
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        reply_markup=orders_list_kb(chunk, page=page, has_prev=has_prev, has_next=has_next, scope=scope),
    )


# =========================
# order detail / items / history / item card
# =========================
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

    # security
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

    is_arch = await TelegramShopOrdersArchiveRepo.is_archived(tenant_id, user_id, oid)

    # порахуємо кількість товарів (без окремого SQL — просто list_order_items)
    items = await TelegramShopOrdersRepo.list_order_items(int(oid))
    items_count = len(items or [])

    text = (
        f"🧾 *Замовлення*\n\n"
        f"Статус: *{st}*\n"
        f"Сума: *{total}*\n"
        f"Створено: _{created}_\n\n"
        "ℹ️ Тут буде історія змін статусів і в майбутньому інтеграція Нової Пошти (події треку)."
    )

    await _send_or_edit_text(
        bot,
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        reply_markup=order_detail_kb(oid, is_archived=bool(is_arch), page=page, scope=scope, items_count=items_count),
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

    items = await TelegramShopOrdersRepo.list_order_items(int(order_id)) or []

    text = (
        f"📦 *Товари в замовленні*\n\n"
        "Натисни на товар, щоб відкрити картку 👇"
    )

    await _send_or_edit_text(
        bot,
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        reply_markup=order_items_list_kb(int(order_id), items, page=page, scope=scope),
    )


async def send_order_history(
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
    """
    Поки що без БД-історії (бо таблиці ще нема) — покажемо зрозумілу “хронологію-мінімум”.
    Коли додаси таблицю історії — тут просто замінимо на реальні події.
    """
    o = await TelegramShopOrdersRepo.get_order(tenant_id, int(order_id))
    if not o:
        await _send_or_edit_text(
            bot,
            chat_id=chat_id,
            message_id=message_id,
            text="📜 *Історія статусів*\n\nЗамовлення не знайдено 😅",
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

    created = _fmt_dt(int(o.get("created_ts") or 0))
    st_raw = str(o.get("status") or "")
    st = status_label(st_raw)

    lines = [
        "📜 *Історія статусів*",
        "",
        f"• `{created}` — *Створено*",
        f"• `{_fmt_dt(int(o.get('created_ts') or 0))}` — Поточний статус: *{st}*",
        "",
        "ℹ️ Далі додамо повну історію (прийнято → упаковано → відправлено → доставлено),",
        "і зможемо підв’язати події напряму з Нової Пошти.",
    ]

    await _send_or_edit_text(
        bot,
        chat_id=chat_id,
        message_id=message_id,
        text="\n".join(lines),
        reply_markup=order_history_back_kb(int(order_id), page=page, scope=scope),
    )


async def send_order_item_card(
    bot: Bot,
    chat_id: int,
    tenant_id: str,
    user_id: int,
    order_id: int,
    product_id: int,
    *,
    page: int = 0,
    scope: str = "active",
    message_id: int | None = None,
) -> None:
    """
    Картка товару як в каталозі (по відчуттю): фото + опис + ціна.
    """
    # (додаткова безпека) перевіримо, що це замовлення юзера
    o = await TelegramShopOrdersRepo.get_order(tenant_id, int(order_id))
    if not o or int(o.get("user_id") or 0) != int(user_id):
        await _send_or_edit_text(
            bot,
            chat_id=chat_id,
            message_id=message_id,
            text="⛔ Нема доступу до цього замовлення.",
            reply_markup=None,
        )
        return

    p = await ProductsRepo.get_active(tenant_id, int(product_id))
    if not p:
        await _send_or_edit_text(
            bot,
            chat_id=chat_id,
            message_id=message_id,
            text="🛍 *Товар*\n\nТовар зараз недоступний (можливо, видалений/деактивований).",
            reply_markup=order_item_back_kb(int(order_id), page=page, scope=scope),
        )
        return

    pid = int(p.get("id") or product_id)
    name = str(p.get("name") or "Товар")
    desc = (p.get("description") or "").strip()
    price_kop = int(p.get("price_kop") or 0)

    text = f"🛍 *{name}*\n\nЦіна: *{_fmt_money(price_kop)}*\nID: `{pid}`"
    if desc:
        text += f"\n\n{desc}"

    cover_file_id = await ProductsRepo.get_cover_photo_file_id(tenant_id, pid)

    await _send_or_edit_product_card(
        bot,
        chat_id=chat_id,
        message_id=message_id,
        file_id=cover_file_id,
        text=text,
        reply_markup=order_item_back_kb(int(order_id), page=page, scope=scope),
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
      tgord:item:<order_id>:<product_id>:<page>:<scope>
      tgord:history:<order_id>:<page>:<scope>
      tgord:arch:<order_id>:<page>:<scope>      (toggle archive)
      tgord:toggle_scope:<page>:<scope>         (switch active<->arch)
    scope: "active" | "arch"
    """
    if not payload.startswith("tgord:"):
        return False

    parts = payload.split(":")
    action = parts[1] if len(parts) > 1 else ""

    def _p_int(idx: int, default: int = 0) -> int:
        if len(parts) > idx and str(parts[idx]).isdigit():
            return int(parts[idx])
        return default

    def _p_scope(idx: int, default: str = "active") -> str:
        if len(parts) > idx and parts[idx] in ("active", "arch"):
            return parts[idx]
        return default

    # list
    if action == "list":
        page = _p_int(2, 0)
        scope = _p_scope(3, "active")
        await send_orders_list(bot, chat_id, tenant_id, user_id, page=page, scope=scope, message_id=message_id)
        return True

    # open
    if action == "open":
        oid = _p_int(2, 0)
        page = _p_int(3, 0)
        scope = _p_scope(4, "active")
        if oid > 0:
            await send_order_detail(bot, chat_id, tenant_id, user_id, oid, page=page, scope=scope, message_id=message_id)
        return True

    # items
    if action == "items":
        oid = _p_int(2, 0)
        page = _p_int(3, 0)
        scope = _p_scope(4, "active")
        if oid > 0:
            await send_order_items(bot, chat_id, tenant_id, user_id, oid, page=page, scope=scope, message_id=message_id)
        return True

    # item card
    if action == "item":
        oid = _p_int(2, 0)
        pid = _p_int(3, 0)
        page = _p_int(4, 0)
        scope = _p_scope(5, "active")
        if oid > 0 and pid > 0:
            await send_order_item_card(
                bot, chat_id, tenant_id, user_id,
                oid, pid,
                page=page, scope=scope, message_id=message_id
            )
        return True

    # history
    if action == "history":
        oid = _p_int(2, 0)
        page = _p_int(3, 0)
        scope = _p_scope(4, "active")
        if oid > 0:
            await send_order_history(bot, chat_id, tenant_id, user_id, oid, page=page, scope=scope, message_id=message_id)
        return True

    # toggle archive
    if action == "arch":
        oid = _p_int(2, 0)
        page = _p_int(3, 0)
        scope = _p_scope(4, "active")
        if oid > 0:
            await TelegramShopOrdersArchiveRepo.toggle(tenant_id, user_id, oid)
            await send_order_detail(bot, chat_id, tenant_id, user_id, oid, page=page, scope=scope, message_id=message_id)
        return True

    # switch active<->arch
    if action == "toggle_scope":
        page = _p_int(2, 0)
        scope = _p_scope(3, "active")
        new_scope = "arch" if scope == "active" else "active"
        await send_orders_list(bot, chat_id, tenant_id, user_id, page=page, scope=new_scope, message_id=message_id)
        return True

    return True