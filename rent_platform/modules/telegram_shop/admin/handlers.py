# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from typing import Any

from aiogram import Bot
from aiogram.types import InputMediaPhoto

from rent_platform.modules.telegram_shop.repo.support_links import TelegramShopSupportLinksRepo
from rent_platform.db.session import db_fetch_all, db_fetch_one, db_execute  # noqa: F401
from rent_platform.modules.telegram_shop.admin_orders import admin_orders_handle_update
from rent_platform.modules.telegram_shop.repo.products import ProductsRepo
from rent_platform.modules.telegram_shop.channel_announce import maybe_post_new_product

# CategoriesRepo optional (if file exists)
try:
    from rent_platform.modules.telegram_shop.repo.categories import CategoriesRepo  # type: ignore
except Exception:  # pragma: no cover
    CategoriesRepo = None  # type: ignore


# ============================================================
# In-memory wizard state
# key: (tenant_id, chat_id) -> state dict
# ============================================================
_STATE: dict[tuple[str, int], dict[str, Any]] = {}


# ============================================================
# Helpers
# ============================================================
def _fmt_money(kop: int) -> str:
    kop = int(kop or 0)
    uah = kop // 100
    cents = kop % 100
    return f"{uah}.{cents:02d} грн"


def _parse_price_to_kop(raw: str) -> int | None:
    """
    Accepts:
      - "1200" => 1200 грн
      - "1200.50" / "1200,50" => 1200 грн 50 коп
      - "1200 грн"
    Returns копійки.
    """
    s = (raw or "").lower().replace("грн", "").replace("uah", "").strip()
    s = s.replace(" ", "").replace(",", ".")
    if not s:
        return None

    if "." in s:
        left, right = (s.split(".", 1) + ["0"])[:2]
        if not left.isdigit():
            return None
        uah = int(left)
        right = "".join(ch for ch in right if ch.isdigit())
        cents = int((right + "0")[:2]) if right else 0
        return uah * 100 + cents

    if not s.isdigit():
        return None
    val = int(s)
    if val <= 200000:
        return val * 100
    return val


def _fmt_dt(ts: int) -> str:
    try:
        import datetime as _dt
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("Europe/Kyiv")
        return _dt.datetime.fromtimestamp(int(ts), tz=tz).strftime("%d.%m.%Y %H:%M")
    except Exception:
        try:
            import datetime as _dt

            return _dt.datetime.fromtimestamp(int(ts)).strftime("%d.%m.%Y %H:%M")
        except Exception:
            return str(ts)


def _parse_dt_to_ts(raw: str) -> int | None:
    """Parse `DD.MM.YYYY HH:MM` to unix ts (Europe/Kyiv if available)."""
    s = (raw or "").strip()
    if not s:
        return None
    if s in ("0", "-", "без", "безкінечно", "безконечно", "never", "no"):
        return 0
    try:
        import datetime as _dt
        from zoneinfo import ZoneInfo

        dt = _dt.datetime.strptime(s, "%d.%m.%Y %H:%M")
        try:
            tz = ZoneInfo("Europe/Kyiv")
            dt = dt.replace(tzinfo=tz)
        except Exception:
            pass
        return int(dt.timestamp())
    except Exception:
        return None


def _extract_message(data: dict[str, Any]) -> dict | None:
    return data.get("message") or data.get("edited_message")


def _extract_callback(data: dict[str, Any]) -> dict | None:
    return data.get("callback_query")


def _kb(rows: list[list[tuple[str, str]]]) -> dict:
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for (t, d) in row] for row in rows]}


def _state_get(tenant_id: str, chat_id: int) -> dict[str, Any] | None:
    return _STATE.get((tenant_id, chat_id))


def _state_set(tenant_id: str, chat_id: int, st: dict[str, Any]) -> None:
    _STATE[(tenant_id, chat_id)] = st


def _state_clear(tenant_id: str, chat_id: int) -> None:
    _STATE.pop((tenant_id, chat_id), None)


def _safe_name(s: str, n: int = 28) -> str:
    s = (s or "").strip()
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"


def _safe_btn(s: str, n: int = 60) -> str:
    s = (s or "").strip()
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"


def _extract_image_file_id(msg: dict) -> str | None:
    photos = msg.get("photo") or []
    if photos:
        return str(photos[-1].get("file_id"))

    doc = msg.get("document")
    if doc:
        mime = (doc.get("mime_type") or "").lower()
        if mime.startswith("image/"):
            return str(doc.get("file_id"))

    return None


# ============================================================
# Menus
# ============================================================
def _admin_home_kb() -> dict:
    return _kb(
        [
            [("📦 Каталог", "tgadm:catalog")],
            [("🧾 Замовлення", "tgadm:ord_menu:0")],
            [("🆘 Підтримка", "tgadm:sup_menu")],
            [("❌ Скинути дію", "tgadm:cancel")],
        ]
    )


def _catalog_kb() -> dict:
    return _kb(
        [
            [("📁 Категорії", "tgadm:cat_menu"), ("📦 Товари", "tgadm:prod_menu")],
            [("🗃 Архів (вимкнені)", "tgadm:archive:0"), ("🔥 Акції / Знижки", "tgadm:promos")],
            [("🏠 В адмін-меню", "tgadm:home")],
        ]
    )


def _products_menu_kb() -> dict:
    return _kb(
        [
            [("➕ Додати товар", "tgadm:wiz_start"), ("📦 Список активних", "tgadm:listp:0")],
            [("⛔ Вимкнути (ID)", "tgadm:disable"), ("✅ Увімкнути (ID)", "tgadm:enable")],
            [("⬅️ Назад", "tgadm:catalog")],
        ]
    )


def _categories_menu_kb(*, default_visible: bool, show_all_enabled: bool) -> dict:
    eye = "👁 ON" if default_visible else "🙈 OFF"
    allb = "🌐 ON" if show_all_enabled else "🌐 OFF"
    return _kb(
        [
            [("➕ Додати категорію", "tgadm:cat_create"), ("🧩 Керувати категорією", "tgadm:cat_manage")],
            [("🗑 Видалити категорію", "tgadm:cat_delete")],
            [(f"{eye}  'Без категорії'", "tgadm:toggle_default"), (f"{allb}  'Усі товари'", "tgadm:toggle_allbtn")],
            [("⬅️ Назад", "tgadm:catalog")],
        ]
    )


def _promos_kb() -> dict:
    return _kb(
        [
            [("➕ Додати акцію (ID)", "tgadm:promo_add"), ("📋 Акційні товари", "tgadm:promo_list:0")],
            [("⬅️ Назад", "tgadm:catalog")],
        ]
    )


def _promos_list_kb(items: list[dict[str, Any]], *, page: int, has_next: bool) -> dict:
    rows: list[list[tuple[str, str]]] = []
    for p in items:
        pid = int(p["id"])
        name = str(p.get("name") or "")
        sku = str(p.get("sku") or "").strip()
        title = _safe_name(name, 26)
        label = f"🔥 #{pid} {title}"
        if sku:
            label = f"🔥 #{pid} {sku} {title}"
        rows.append([(_safe_btn(label, 60), f"tgadm:promo_open:{pid}:0")])

    nav: list[tuple[str, str]] = []
    nav.append(("⬅️", f"tgadm:promo_list:{page-1}:0") if page > 0 else ("·", "tgadm:noop"))
    nav.append(("➡️", f"tgadm:promo_list:{page+1}:0") if has_next else ("·", "tgadm:noop"))
    rows.append(nav)
    rows.append([("⬅️ Акції", "tgadm:promos")])
    return _kb(rows)


def _products_list_kb(items: list[dict[str, Any]], *, page: int, has_next: bool) -> dict:
    rows: list[list[tuple[str, str]]] = []
    for p in items:
        pid = int(p["id"])
        name = str(p.get("name") or "")
        sku = str(p.get("sku") or "").strip()
        price = _fmt_money(int(p.get("price_kop") or 0))
        title = _safe_name(name, 22)

        label = f"📦 #{pid} {title} | {price}"
        if sku:
            label = f"📦 #{pid} {sku} {title} | {price}"

        rows.append([(_safe_btn(label, 60), f"tgadm:p_open:{pid}:0")])

    nav: list[tuple[str, str]] = []
    nav.append(("⬅️", f"tgadm:listp:{page-1}:0") if page > 0 else ("·", "tgadm:noop"))
    nav.append(("➡️", f"tgadm:listp:{page+1}:0") if has_next else ("·", "tgadm:noop"))
    rows.append(nav)
    rows.append([("⬅️ Назад", "tgadm:prod_menu")])
    return _kb(rows)


def _promo_product_card_kb(*, product_id: int, category_id: int, has_prev: bool, has_next: bool, promo_active: bool) -> dict:
    cid = int(category_id)
    nav_row: list[tuple[str, str]] = []
    nav_row.append(("⬅️", f"tgadm:pp_prev:{product_id}:{cid}") if has_prev else ("·", "tgadm:noop"))
    nav_row.append(("➡️", f"tgadm:pp_next:{product_id}:{cid}") if has_next else ("·", "tgadm:noop"))

    clear_btn = ("❌ Зняти акцію", f"tgadm:promo_clear:{product_id}:{cid}") if promo_active else ("·", "tgadm:noop")

    return _kb(
        [
            nav_row,
            [clear_btn, ("➕/✏️ Налаштувати", f"tgadm:promo_edit:{product_id}:{cid}")],
            [("💸 Ціна акції", f"tgadm:promo_price:{product_id}:{cid}"), ("⏰ До", f"tgadm:promo_until:{product_id}:{cid}")],
            [("⬅️ Акції", "tgadm:promos")],
        ]
    )


def _wiz_nav_kb(*, allow_skip: bool = False) -> dict:
    row: list[tuple[str, str]] = [("❌ Скасувати", "tgadm:cancel")]
    if allow_skip:
        row.insert(0, ("⏭ Пропустити", "tgadm:wiz_skip"))
    return _kb([row])


def _wiz_promo_kb() -> dict:
    return _kb(
        [
            [("🚫 Не буде акції", "tgadm:wiz_no_promo")],
            [("❌ Скасувати", "tgadm:cancel")],
        ]
    )


def _wiz_photos_kb(*, product_id: int) -> dict:
    return _kb(
        [
            [("📷 Додати ще фото", "tgadm:wiz_photo_more"), ("✅ Готово", "tgadm:wiz_done")],
            [("📝 Додати/змінити опис", f"tgadm:wiz_desc_edit:{product_id}")],
            [("❌ Скасувати", "tgadm:cancel")],
        ]
    )


def _wiz_finish_kb(*, product_id: int) -> dict:
    return _kb(
        [
            [("📷 Додати фото", f"tgadm:wiz_photo_more:{product_id}"), ("📝 Опис", f"tgadm:wiz_desc_edit:{product_id}")],
            [("➕ Додати ще товар", "tgadm:wiz_start"), ("📦 Товари", "tgadm:prod_menu")],
            [("📦 Каталог", "tgadm:catalog")],
        ]
    )


def _category_pick_kb(categories: list[dict], *, prefix: str, back_to: str) -> dict:
    rows: list[list[tuple[str, str]]] = []
    for c in categories:
        cid = int(c["id"])
        name = str(c["name"])
        if name.startswith("__"):
            continue
        rows.append([(f"📁 {name}", f"{prefix}:{cid}")])
    rows.append([("⬅️ Назад", back_to), ("❌ Скасувати", "tgadm:cancel")])
    return _kb(rows)


def _admin_product_card_kb(*, product_id: int, category_id: int, has_prev: bool, has_next: bool) -> dict:
    cid = int(category_id)
    nav_row: list[tuple[str, str]] = []
    nav_row.append(("⬅️", f"tgadm:pc_prev:{product_id}:{cid}") if has_prev else ("·", "tgadm:noop"))
    nav_row.append(("➡️", f"tgadm:pc_next:{product_id}:{cid}") if has_next else ("·", "tgadm:noop"))

    return _kb(
        [
            nav_row,
            [("🗃 В архів", f"tgadm:p_to_arch:{product_id}:{cid}"), ("✅ Увімкн.", f"tgadm:p_enable:{product_id}:{cid}")],
            [("🔥 Акція", f"tgadm:promo_open:{product_id}:{cid}"), ("🏷 SKU", f"tgadm:psku:{product_id}:{cid}")],
            [("📁 Категорія", f"tgadm:p_setcat:{product_id}:{cid}"), ("📝 Опис", f"tgadm:wiz_desc_edit:{product_id}")],
            [("📷 Додати фото", f"tgadm:p_photo:{product_id}:{cid}"), ("💰 Ціна", f"tgadm:pprice:{product_id}:{cid}")],
            [("✏️ Назва", f"tgadm:pname:{product_id}:{cid}"), ("⬅️ Категорії", "tgadm:cat_manage")],
        ]
    )


def _archive_list_kb(items: list[dict[str, Any]], *, page: int, has_next: bool) -> dict:
    rows: list[list[tuple[str, str]]] = []
    for p in items:
        pid = int(p["id"])
        name = str(p.get("name") or "")
        sku = str(p.get("sku") or "").strip()
        title = _safe_name(name, 24)
        label = f"📦 #{pid} {title}"
        if sku:
            label = f"📦 #{pid} {sku} {title}"
        rows.append([(_safe_btn(label, 60), f"tgadm:arch_open:{pid}")])

    nav: list[tuple[str, str]] = []
    nav.append(("⬅️", f"tgadm:archive:{page-1}") if page > 0 else ("·", "tgadm:noop"))
    nav.append(("➡️", f"tgadm:archive:{page+1}") if has_next else ("·", "tgadm:noop"))
    rows.append(nav)
    rows.append([("⬅️ Назад", "tgadm:catalog")])
    return _kb(rows)


def _archive_product_kb(*, product_id: int) -> dict:
    return _kb(
        [
            [("✅ Увімкнути", f"tgadm:arch_enable:{product_id}"), ("📁 Категорія", f"tgadm:arch_setcat:{product_id}")],
            [("🏷 SKU", f"tgadm:arch_sku:{product_id}"), ("✏️ Назва", f"tgadm:arch_name:{product_id}")],
            [("💰 Ціна", f"tgadm:arch_price:{product_id}"), ("📷 Фото", f"tgadm:arch_photo:{product_id}")],
            [("📝 Опис", f"tgadm:wiz_desc_edit:{product_id}")],
            [("⬅️ До архіву", "tgadm:archive:0"), ("🏠 Каталог", "tgadm:catalog")],
        ]
    )


# ============================================================
# SUPPORT (admin)
# tgadm:sup_menu
# tgadm:sup_open:<key>
# tgadm:sup_toggle:<key>
# tgadm:sup_edit_title:<key>
# tgadm:sup_edit_url:<key>
# ============================================================
def _sup_list_kb(items: list[dict[str, Any]]) -> dict:
    rows: list[list[tuple[str, str]]] = []
    for it in items:
        k = str(it.get("key") or "")
        t = str(it.get("title") or k)
        en = bool(it.get("enabled"))
        mark = "✅" if en else "⛔"
        rows.append([(_safe_btn(f"{mark} {t}", 60), f"tgadm:sup_open:{k}")])
    rows.append([("⬅️ В адмін-меню", "tgadm:home")])
    return _kb(rows)


def _sup_item_kb(key: str, enabled: bool) -> dict:
    tog = "⛔ Вимкнути" if enabled else "✅ Увімкнути"
    return _kb(
        [
            [(tog, f"tgadm:sup_toggle:{key}")],
            [("✏️ Назва", f"tgadm:sup_edit_title:{key}"), ("🔗 Значення/URL", f"tgadm:sup_edit_url:{key}")],
            [("⬅️ Назад", "tgadm:sup_menu")],
        ]
    )


# ============================================================
# Senders
# ============================================================
async def _send_admin_home(bot: Bot, chat_id: int) -> None:
    await bot.send_message(
        chat_id,
        "🛠 *Адмінка магазину*\n\nОдна точка входу — *📦 Каталог* 👇",
        parse_mode="Markdown",
        reply_markup=_admin_home_kb(),
    )


async def _send_catalog_home(bot: Bot, chat_id: int) -> None:
    await bot.send_message(
        chat_id,
        "📦 *Каталог*\n\nОбери розділ 👇",
        parse_mode="Markdown",
        reply_markup=_catalog_kb(),
    )


async def _send_categories_menu(bot: Bot, chat_id: int, tenant_id: str) -> None:
    if CategoriesRepo is None:
        await bot.send_message(chat_id, "📁 Категорії ще не підключені (repo/categories.py).", reply_markup=_catalog_kb())
        return

    await CategoriesRepo.ensure_default(tenant_id)  # type: ignore[misc]
    await CategoriesRepo.ensure_show_all_flag(tenant_id)  # type: ignore[misc]
    default_visible = await CategoriesRepo.is_default_visible(tenant_id)  # type: ignore[misc]
    show_all_enabled = await CategoriesRepo.is_show_all_enabled(tenant_id)  # type: ignore[misc]

    await bot.send_message(
        chat_id,
        "📁 *Категорії*\n\nОбери дію 👇",
        parse_mode="Markdown",
        reply_markup=_categories_menu_kb(default_visible=bool(default_visible), show_all_enabled=bool(show_all_enabled)),
    )


async def _send_products_list_inline(bot: Bot, chat_id: int, tenant_id: str, page: int) -> None:
    page = max(0, int(page))
    limit = 12
    offset = page * limit

    rows = await ProductsRepo.list_active(tenant_id, limit=500)
    rows_sorted = sorted(rows, key=lambda x: int(x["id"]), reverse=True)

    chunk = rows_sorted[offset : offset + limit]
    has_next = len(rows_sorted) > offset + limit

    if not chunk:
        await bot.send_message(chat_id, "Поки що немає активних товарів.", reply_markup=_catalog_kb())
        return

    await bot.send_message(
        chat_id,
        "📦 *Активні товари*\n\nНатисни товар 👇",
        parse_mode="Markdown",
        reply_markup=_products_list_kb(chunk, page=page, has_next=has_next),
    )


async def _send_promos_home(bot: Bot, chat_id: int, tenant_id: str) -> None:
    now = int(time.time())
    q = """
    SELECT COUNT(*) AS cnt
    FROM telegram_shop_products
    WHERE tenant_id = :tid
      AND is_active = true
      AND COALESCE(promo_price_kop, 0) > 0
      AND (COALESCE(promo_until_ts, 0) = 0 OR COALESCE(promo_until_ts, 0) > :now)
    """
    row = await db_fetch_one(q, {"tid": tenant_id, "now": now}) or {}
    cnt = int(row.get("cnt") or 0)

    await bot.send_message(
        chat_id,
        f"🔥 *Акції / Знижки*\n\nАктивних акцій: *{cnt}*\n\n"
        "Формат дати: `DD.MM.YYYY HH:MM` (наприклад `31.01.2026 18:30`).\n"
        "Можна ввести `0`, щоб зробити *без кінцевої дати*.",
        parse_mode="Markdown",
        reply_markup=_promos_kb(),
    )


async def _send_promos_list(bot: Bot, chat_id: int, tenant_id: str, page: int) -> None:
    now = int(time.time())
    page = max(0, int(page))
    limit = 12
    offset = page * limit

    q = """
    SELECT id, name, COALESCE(sku,'') AS sku, promo_price_kop, promo_until_ts
    FROM telegram_shop_products
    WHERE tenant_id = :tid
      AND is_active = true
      AND COALESCE(promo_price_kop, 0) > 0
      AND (COALESCE(promo_until_ts, 0) = 0 OR COALESCE(promo_until_ts, 0) > :now)
    ORDER BY CASE WHEN promo_until_ts = 0 THEN 2147483647 ELSE promo_until_ts END ASC, id DESC
    """
    rows = await db_fetch_all(q, {"tid": tenant_id, "now": now}) or []
    chunk = rows[offset : offset + limit]
    has_next = len(rows) > offset + limit

    if not chunk:
        await bot.send_message(chat_id, "Поки що немає активних акцій.", reply_markup=_promos_kb())
        return

    await bot.send_message(
        chat_id,
        "🔥 *Акційні товари*\n\nНатисни товар 👇",
        parse_mode="Markdown",
        reply_markup=_promos_list_kb(chunk, page=page, has_next=has_next),
    )


async def _get_product_any(tenant_id: str, product_id: int) -> dict | None:
    q = """
    SELECT id, tenant_id, category_id, name, COALESCE(sku,'') AS sku, price_kop, is_active,
           COALESCE(is_hit, false) AS is_hit,
           COALESCE(promo_price_kop, 0) AS promo_price_kop,
           COALESCE(promo_until_ts, 0) AS promo_until_ts,
           COALESCE(description,'') AS description
    FROM telegram_shop_products
    WHERE tenant_id = :tid AND id = :pid
    LIMIT 1
    """
    return await db_fetch_one(q, {"tid": tenant_id, "pid": int(product_id)})


async def _build_promo_product_card(tenant_id: str, product_id: int, category_id: int | None) -> dict | None:
    p = await _get_product_any(tenant_id, product_id)
    if not p or not bool(p.get("is_active")):
        return None

    pid = int(p["id"])
    name = str(p.get("name") or "")
    sku = str(p.get("sku") or "").strip()
    price = int(p.get("price_kop") or 0)
    promo_price = int(p.get("promo_price_kop") or 0)
    promo_until = int(p.get("promo_until_ts") or 0)
    desc = (p.get("description") or "").strip()

    cat = category_id if (category_id and category_id > 0) else None
    prev_p = await ProductsRepo.get_prev_active(tenant_id, pid, category_id=cat)
    next_p = await ProductsRepo.get_next_active(tenant_id, pid, category_id=cat)

    cover_file_id = await ProductsRepo.get_cover_photo_file_id(tenant_id, pid)

    now = int(time.time())
    promo_active = promo_price > 0 and (promo_until == 0 or promo_until > now)

    text = f"🔥 *{name}*\n\nБазова ціна: *{_fmt_money(price)}*\nID: `{pid}`"
    if sku:
        text += f"\nSKU: `{sku}`"

    if promo_active:
        until_txt = "без кінця" if promo_until == 0 else _fmt_dt(promo_until)
        text += f"\n\n✅ *Акція активна*\nЦіна акції: *{_fmt_money(promo_price)}*\nДо: *{until_txt}*"
    else:
        text += "\n\nℹ️ Акція зараз *не активна* (можеш налаштувати)."

    if desc:
        text += f"\n\n{desc}"

    kb = _promo_product_card_kb(
        product_id=pid,
        category_id=int(category_id or 0),
        has_prev=bool(prev_p),
        has_next=bool(next_p),
        promo_active=promo_active,
    )
    return {"pid": pid, "file_id": cover_file_id, "has_photo": bool(cover_file_id), "text": text, "kb": kb}


async def _send_promo_product_card(bot: Bot, chat_id: int, tenant_id: str, product_id: int, category_id: int | None) -> None:
    card = await _build_promo_product_card(tenant_id, int(product_id), category_id)
    if not card:
        await bot.send_message(chat_id, "❌ Товар не знайдено або він не активний.", reply_markup=_promos_kb())
        return

    if card["has_photo"]:
        await bot.send_photo(chat_id, photo=card["file_id"], caption=card["text"], parse_mode="Markdown", reply_markup=card["kb"])
    else:
        await bot.send_message(chat_id, card["text"], parse_mode="Markdown", reply_markup=card["kb"])


async def _edit_promo_product_card(bot: Bot, chat_id: int, message_id: int, tenant_id: str, product_id: int, category_id: int | None) -> bool:
    card = await _build_promo_product_card(tenant_id, int(product_id), category_id)
    if not card:
        return False

    if card["has_photo"]:
        media = InputMediaPhoto(media=card["file_id"], caption=card["text"], parse_mode="Markdown")
        await bot.edit_message_media(media=media, chat_id=chat_id, message_id=message_id, reply_markup=card["kb"])
    else:
        await bot.edit_message_text(card["text"], chat_id=chat_id, message_id=message_id, parse_mode="Markdown", reply_markup=card["kb"])
    return True


# ============================================================
# Archive
# ============================================================
async def _send_archive(bot: Bot, chat_id: int, tenant_id: str, page: int) -> None:
    page = max(0, int(page))
    limit = 12
    offset = page * limit

    rows = await ProductsRepo.list_inactive(tenant_id, limit=500)  # type: ignore[attr-defined]
    rows_sorted = sorted(rows, key=lambda x: int(x["id"]), reverse=True)

    chunk = rows_sorted[offset : offset + limit]
    has_next = len(rows_sorted) > offset + limit

    if not chunk:
        await bot.send_message(chat_id, "🗃 Архів порожній (вимкнених товарів нема).", reply_markup=_catalog_kb())
        return

    await bot.send_message(
        chat_id,
        "🗃 *Архів (вимкнені)*\n\nНатисни товар 👇",
        parse_mode="Markdown",
        reply_markup=_archive_list_kb(chunk, page=page, has_next=has_next),
    )


async def _send_archive_product(bot: Bot, chat_id: int, tenant_id: str, product_id: int) -> None:
    p = await _get_product_any(tenant_id, product_id)
    if not p:
        await bot.send_message(chat_id, "❌ Товар не знайдено.", reply_markup=_catalog_kb())
        return

    pid = int(p["id"])
    name = str(p.get("name") or "")
    sku = str(p.get("sku") or "").strip()
    price = int(p.get("price_kop") or 0)
    desc = (p.get("description") or "").strip()
    is_active = bool(p.get("is_active"))

    cover_file_id = await ProductsRepo.get_cover_photo_file_id(tenant_id, pid)

    text = (
        f"📦 *{name}*\n\n"
        f"Ціна: *{_fmt_money(price)}*\n"
        f"ID: `{pid}`\n"
        f"Статус: *{'✅ активний' if is_active else '🗃 в архіві'}*"
    )
    if sku:
        text += f"\nSKU: `{sku}`"
    if desc:
        text += f"\n\n{desc}"

    kb = _archive_product_kb(product_id=pid)

    if cover_file_id:
        await bot.send_photo(chat_id, photo=cover_file_id, caption=text, parse_mode="Markdown", reply_markup=kb)
    else:
        await bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=kb)


# ============================================================
# Category browsing (admin cards)
# ============================================================
async def _send_manage_categories_pick(bot: Bot, chat_id: int, tenant_id: str) -> None:
    if CategoriesRepo is None:
        await bot.send_message(chat_id, "📁 Категорії ще не підключені (repo/categories.py).", reply_markup=_catalog_kb())
        return

    await CategoriesRepo.ensure_default(tenant_id)  # type: ignore[misc]
    cats = await CategoriesRepo.list(tenant_id, limit=100)  # type: ignore[misc]

    await bot.send_message(
        chat_id,
        "🧩 *Керувати категорією*\n\nОбери категорію 👇",
        parse_mode="Markdown",
        reply_markup=_category_pick_kb(cats, prefix="tgadm:cat_open", back_to="tgadm:cat_menu"),
    )


async def _send_delete_categories_pick(bot: Bot, chat_id: int, tenant_id: str) -> None:
    if CategoriesRepo is None:
        await bot.send_message(chat_id, "📁 Категорії ще не підключені (repo/categories.py).", reply_markup=_catalog_kb())
        return

    default_id = await CategoriesRepo.ensure_default(tenant_id)  # type: ignore[misc]
    cats = await CategoriesRepo.list(tenant_id, limit=100)  # type: ignore[misc]
    cats2 = [c for c in cats if int(c["id"]) != int(default_id) and not str(c["name"]).startswith("__")]

    if not cats2:
        await bot.send_message(chat_id, "Нема категорій для видалення (є лише 'Без категорії').", reply_markup=_catalog_kb())
        return

    await bot.send_message(
        chat_id,
        "🗑 *Видалити категорію*\n\nОбери категорію (товари перейдуть в 'Без категорії'):",
        parse_mode="Markdown",
        reply_markup=_category_pick_kb(cats2, prefix="tgadm:cat_del", back_to="tgadm:cat_menu"),
    )


async def _build_admin_product_card(tenant_id: str, product_id: int, category_id: int | None) -> dict | None:
    p = await ProductsRepo.get_active(tenant_id, product_id)
    if not p:
        return None

    cat = category_id if (category_id and category_id > 0) else None
    prev_p = await ProductsRepo.get_prev_active(tenant_id, product_id, category_id=cat)
    next_p = await ProductsRepo.get_next_active(tenant_id, product_id, category_id=cat)

    pid = int(p["id"])
    name = str(p.get("name") or "")
    sku = str(p.get("sku") or "").strip()
    price = int(p.get("price_kop") or 0)
    desc = (p.get("description") or "").strip()

    cover_file_id = await ProductsRepo.get_cover_photo_file_id(tenant_id, pid)

    text = f"🛍 *{name}*\n\nЦіна: *{_fmt_money(price)}*\nID: `{pid}`"
    if sku:
        text += f"\nSKU: `{sku}`"
    if desc:
        text += f"\n\n{desc}"

    kb = _admin_product_card_kb(
        product_id=pid,
        category_id=int(category_id or 0),
        has_prev=bool(prev_p),
        has_next=bool(next_p),
    )
    return {"pid": pid, "file_id": cover_file_id, "has_photo": bool(cover_file_id), "text": text, "kb": kb}


async def _send_admin_category_first_product(bot: Bot, chat_id: int, tenant_id: str, category_id: int) -> None:
    p = await ProductsRepo.get_first_active(tenant_id, category_id=category_id)
    if not p:
        await bot.send_message(chat_id, "У цій категорії поки що немає активних товарів.", reply_markup=_catalog_kb())
        return

    card = await _build_admin_product_card(tenant_id, int(p["id"]), int(category_id))
    if not card:
        await bot.send_message(chat_id, "Категорія порожня.", reply_markup=_catalog_kb())
        return

    if card["has_photo"]:
        await bot.send_photo(chat_id, photo=card["file_id"], caption=card["text"], parse_mode="Markdown", reply_markup=card["kb"])
    else:
        await bot.send_message(chat_id, card["text"], parse_mode="Markdown", reply_markup=card["kb"])


async def _edit_admin_product_card(bot: Bot, chat_id: int, message_id: int, tenant_id: str, product_id: int, category_id: int | None) -> bool:
    card = await _build_admin_product_card(tenant_id, product_id, category_id)
    if not card:
        return False

    if card["has_photo"]:
        media = InputMediaPhoto(media=card["file_id"], caption=card["text"], parse_mode="Markdown")
        await bot.edit_message_media(media=media, chat_id=chat_id, message_id=message_id, reply_markup=card["kb"])
    else:
        await bot.edit_message_text(card["text"], chat_id=chat_id, message_id=message_id, parse_mode="Markdown", reply_markup=card["kb"])
    return True


# ============================================================
# Wizard: create product
# name -> sku -> price -> promo_price (or no promo) -> desc -> category -> photos
# ============================================================
async def _wiz_ask_name(bot: Bot, chat_id: int, tenant_id: str) -> None:
    _state_set(tenant_id, chat_id, {"mode": "wiz_name", "draft": {}})
    await bot.send_message(
        chat_id,
        "➕ *Новий товар*\n\n1/6 Введи *назву* товару:",
        parse_mode="Markdown",
        reply_markup=_wiz_nav_kb(),
    )


async def _wiz_ask_sku(bot: Bot, chat_id: int, tenant_id: str, draft: dict) -> None:
    _state_set(tenant_id, chat_id, {"mode": "wiz_sku", "draft": draft})
    await bot.send_message(
        chat_id,
        "2/6 Введи *SKU/артикул* (або натисни `Пропустити`):",
        parse_mode="Markdown",
        reply_markup=_wiz_nav_kb(allow_skip=True),
    )


async def _wiz_ask_price(bot: Bot, chat_id: int, tenant_id: str, draft: dict) -> None:
    _state_set(tenant_id, chat_id, {"mode": "wiz_price", "draft": draft})
    await bot.send_message(
        chat_id,
        "3/6 Введи *ціну* (наприклад `1200.50` або `1200`):",
        parse_mode="Markdown",
        reply_markup=_wiz_nav_kb(),
    )


async def _wiz_ask_promo_price(bot: Bot, chat_id: int, tenant_id: str, draft: dict) -> None:
    _state_set(tenant_id, chat_id, {"mode": "wiz_promo_price", "draft": draft})
    await bot.send_message(
        chat_id,
        "4/6 *Акційна ціна*\n\nВведи *акційну ціну* (наприклад `999.99`) або натисни кнопку нижче 👇",
        parse_mode="Markdown",
        reply_markup=_wiz_promo_kb(),
    )


async def _wiz_ask_desc(bot: Bot, chat_id: int, tenant_id: str, draft: dict) -> None:
    _state_set(tenant_id, chat_id, {"mode": "wiz_desc", "draft": draft})
    await bot.send_message(
        chat_id,
        "5/6 Додай *опис* (або натисни `Пропустити`):",
        parse_mode="Markdown",
        reply_markup=_wiz_nav_kb(allow_skip=True),
    )


async def _wiz_ask_category(bot: Bot, chat_id: int, tenant_id: str, draft: dict) -> None:
    if CategoriesRepo is None:
        draft["category_id"] = None
        await _wiz_create_and_go_photos(bot, chat_id, tenant_id, draft)
        return

    default_cid = await CategoriesRepo.ensure_default(tenant_id)  # type: ignore[misc]
    cats = await CategoriesRepo.list(tenant_id, limit=50)  # type: ignore[misc]
    _state_set(
        tenant_id,
        chat_id,
        {"mode": "wiz_category", "draft": draft, "default_category_id": int(default_cid or 0)},
    )

    await bot.send_message(
        chat_id,
        "6/6 *Категорія*\n\nОбери категорію для товару:",
        parse_mode="Markdown",
        reply_markup=_category_pick_kb(cats, prefix="tgadm:wiz_cat", back_to="tgadm:prod_menu"),
    )


async def _wiz_create_product(tenant_id: str, draft: dict) -> int | None:
    name = str(draft.get("name") or "").strip()
    sku = str(draft.get("sku") or "").strip()[:64] or None
    price_kop = int(draft.get("price_kop") or 0)
    desc = str(draft.get("description") or "").strip()

    category_id = draft.get("category_id", None)
    if isinstance(category_id, str) and category_id.isdigit():
        category_id = int(category_id)
    elif category_id is not None and not isinstance(category_id, int):
        category_id = None

    pid = await ProductsRepo.add(tenant_id, name, price_kop, is_active=True, category_id=category_id, sku=sku)  # type: ignore[arg-type]
    if not pid:
        return None

    pid_i = int(pid)

    if desc:
        await ProductsRepo.set_description(tenant_id, pid_i, desc)

    promo_price_kop = int(draft.get("promo_price_kop") or 0)
    promo_until_ts = int(draft.get("promo_until_ts") or 0)
    if promo_price_kop > 0:
        await ProductsRepo.set_promo(tenant_id, pid_i, promo_price_kop, promo_until_ts)

    return pid_i


async def _wiz_create_and_go_photos(bot: Bot, chat_id: int, tenant_id: str, draft: dict) -> None:
    pid = await _wiz_create_product(tenant_id, draft)
    _state_clear(tenant_id, chat_id)

    if not pid:
        await bot.send_message(chat_id, "❌ Не вдалося створити товар (перевір БД/міграції).", reply_markup=_admin_home_kb())
        return

    await _wiz_photos_start(bot, chat_id, tenant_id, pid)


async def _wiz_photos_start(bot: Bot, chat_id: int, tenant_id: str, product_id: int) -> None:
    _state_set(tenant_id, chat_id, {"mode": "wiz_photo", "product_id": int(product_id), "announced": False})
    await bot.send_message(
        chat_id,
        f"📷 Фото для товару *#{product_id}*\n\nНадсилай фото (можна кілька).",
        parse_mode="Markdown",
        reply_markup=_wiz_photos_kb(product_id=product_id),
    )


async def _wiz_finish(bot: Bot, chat_id: int, product_id: int) -> None:
    await bot.send_message(
        chat_id,
        f"✅ *Готово!* Товар *#{product_id}* створено.\n\nМожеш додати фото/опис або створити ще.",
        parse_mode="Markdown",
        reply_markup=_wiz_finish_kb(product_id=product_id),
    )


# ============================================================
# Main entry
# ============================================================
async def handle_update(*, tenant: dict, data: dict[str, Any], bot: Bot) -> bool:
    tenant_id = str(tenant["id"])

    # ---------------- callbacks ----------------
    cb = _extract_callback(data)
    if cb:
        payload = (cb.get("data") or "").strip()
        if not payload.startswith("tgadm:"):
            return False

        chat_id = int(cb["message"]["chat"]["id"])
        msg_id = int(cb["message"]["message_id"])
        cb_id = cb.get("id")
        if cb_id:
            await bot.answer_callback_query(cb_id)

        # ✅ Orders admin module (separate file)
        if payload.startswith("tgadm:ord"):
            handled = await admin_orders_handle_update(tenant=tenant, data=data, bot=bot)
            if handled:
                return True

        parts = payload.split(":")
        action = parts[1] if len(parts) > 1 else ""
        arg = parts[2] if len(parts) > 2 else ""
        arg2 = parts[3] if len(parts) > 3 else ""

        if action == "noop":
            return True

        # HOME / CATALOG
        if action == "home":
            _state_clear(tenant_id, chat_id)
            await _send_admin_home(bot, chat_id)
            return True

        if action == "catalog":
            _state_clear(tenant_id, chat_id)
            await _send_catalog_home(bot, chat_id)
            return True

        if action == "prod_menu":
            _state_clear(tenant_id, chat_id)
            await bot.send_message(chat_id, "📦 *Товари*\n\nОбери дію 👇", parse_mode="Markdown", reply_markup=_products_menu_kb())
            return True

        if action == "cat_menu":
            _state_clear(tenant_id, chat_id)
            await _send_categories_menu(bot, chat_id, tenant_id)
            return True

        # =========================
        # SUPPORT (admin)
        # =========================
        if action == "sup_menu":
            _state_clear(tenant_id, chat_id)
            await TelegramShopSupportLinksRepo.ensure_defaults(tenant_id)
            items = await TelegramShopSupportLinksRepo.list_all(tenant_id)

            await bot.send_message(
                chat_id,
                "🆘 *Підтримка — налаштування*\n\n"
                "Тут вмикаєш/вимикаєш кнопки і міняєш значення.\n\n"
                "ℹ️ Для *Автопост новинок* (`announce_chat_id`):\n"
                "• `Значення/URL` = chat_id каналу (наприклад `-1001234567890`)\n"
                "• увімкни кнопку ✅\n",
                parse_mode="Markdown",
                reply_markup=_sup_list_kb(items),
            )
            return True

        if action == "sup_open" and arg:
            _state_clear(tenant_id, chat_id)
            await TelegramShopSupportLinksRepo.ensure_defaults(tenant_id)
            it = await TelegramShopSupportLinksRepo.get(tenant_id, arg)
            if not it:
                await bot.send_message(chat_id, "❌ Не знайдено.", reply_markup=_admin_home_kb())
                return True

            k = str(it.get("key") or "")
            t = str(it.get("title") or "")
            u = str(it.get("url") or "")
            en = bool(it.get("enabled"))

            txt = (
                "🆘 *Підтримка — кнопка*\n\n"
                f"Key: `{k}`\n"
                f"Назва: *{t}*\n"
                f"Значення: `{u}`\n"
                f"Статус: *{'✅ ON' if en else '⛔ OFF'}*"
            )
            await bot.send_message(chat_id, txt, parse_mode="Markdown", reply_markup=_sup_item_kb(k, en))
            return True

        if action == "sup_toggle" and arg:
            it = await TelegramShopSupportLinksRepo.get(tenant_id, arg)
            if not it:
                return True
            new_val = not bool(it.get("enabled"))
            await TelegramShopSupportLinksRepo.set_enabled(tenant_id, arg, new_val)
            await bot.send_message(
                chat_id,
                f"✅ Збережено: *{'ON' if new_val else 'OFF'}*",
                parse_mode="Markdown",
                reply_markup=_sup_item_kb(arg, new_val),
            )
            return True

        if action == "sup_edit_title" and arg:
            _state_set(tenant_id, chat_id, {"mode": "sup_edit_title", "key": arg})
            await bot.send_message(chat_id, "✏️ Надішли нову *назву* кнопки:", parse_mode="Markdown", reply_markup=_wiz_nav_kb())
            return True

        if action == "sup_edit_url" and arg:
            _state_set(tenant_id, chat_id, {"mode": "sup_edit_url", "key": arg})
            await bot.send_message(
                chat_id,
                "🔗 Надішли *значення/URL*.\n\n"
                "Приклади:\n"
                "• `@yourchannel`\n"
                "• `t.me/yourchat`\n"
                "• `https://site.com`\n"
                "• `support@site.com`\n"
                "• для announce_chat_id: `-1001234567890`",
                parse_mode="Markdown",
                reply_markup=_wiz_nav_kb(),
            )
            return True

        # Wizard: promo quick button (no promo)
        if action == "wiz_no_promo":
            st = _state_get(tenant_id, chat_id) or {}
            draft = st.get("draft") or {}
            draft["promo_price_kop"] = 0
            draft["promo_until_ts"] = 0
            await _wiz_ask_desc(bot, chat_id, tenant_id, draft)
            return True

        # settings toggles
        if action == "toggle_default":
            if CategoriesRepo is None:
                return True
            cur = await CategoriesRepo.is_default_visible(tenant_id)  # type: ignore[misc]
            await CategoriesRepo.set_default_visible(tenant_id, not cur)  # type: ignore[misc]
            await _send_categories_menu(bot, chat_id, tenant_id)
            return True

        if action == "toggle_allbtn":
            if CategoriesRepo is None:
                return True
            cur = await CategoriesRepo.is_show_all_enabled(tenant_id)  # type: ignore[misc]
            await CategoriesRepo.set_show_all_enabled(tenant_id, not cur)  # type: ignore[misc]
            await _send_categories_menu(bot, chat_id, tenant_id)
            return True

        # ARCHIVE
        if action == "archive":
            _state_clear(tenant_id, chat_id)
            page = int(arg) if arg.isdigit() else 0
            await _send_archive(bot, chat_id, tenant_id, page)
            return True

        if action == "arch_open" and arg.isdigit():
            _state_clear(tenant_id, chat_id)
            await _send_archive_product(bot, chat_id, tenant_id, int(arg))
            return True

        if action == "arch_enable" and arg.isdigit():
            pid = int(arg)
            await ProductsRepo.set_active(tenant_id, pid, True)
            await bot.send_message(chat_id, f"✅ Товар {pid} увімкнено.", reply_markup=_catalog_kb())
            return True

        if action == "arch_setcat" and arg.isdigit():
            if CategoriesRepo is None:
                await bot.send_message(chat_id, "Категорії не підключені.", reply_markup=_catalog_kb())
                return True
            pid = int(arg)
            cats = await CategoriesRepo.list(tenant_id, limit=100)  # type: ignore[misc]
            _state_set(tenant_id, chat_id, {"mode": "arch_setcat_pick", "product_id": pid})
            await bot.send_message(
                chat_id,
                "📁 Обери категорію для товару:",
                reply_markup=_category_pick_kb(cats, prefix="tgadm:arch_setcat_do", back_to="tgadm:archive:0"),
            )
            return True

        if action == "arch_setcat_do" and arg.isdigit():
            st = _state_get(tenant_id, chat_id) or {}
            pid = int(st.get("product_id") or 0)
            cid = int(arg)
            if pid:
                await ProductsRepo.set_category(tenant_id, pid, cid)
                _state_clear(tenant_id, chat_id)
                await bot.send_message(chat_id, "✅ Категорію змінено.", reply_markup=_catalog_kb())
            return True

        if action == "arch_name" and arg.isdigit():
            _state_set(tenant_id, chat_id, {"mode": "arch_edit_name", "product_id": int(arg)})
            await bot.send_message(chat_id, f"✏️ Надішли нову назву для товару #{arg}:", reply_markup=_wiz_nav_kb())
            return True

        if action == "arch_price" and arg.isdigit():
            _state_set(tenant_id, chat_id, {"mode": "arch_edit_price", "product_id": int(arg)})
            await bot.send_message(chat_id, f"💰 Надішли нову ціну для товару #{arg} (1200.50):", reply_markup=_wiz_nav_kb())
            return True

        if action == "arch_photo" and arg.isdigit():
            _state_set(tenant_id, chat_id, {"mode": "arch_add_photo", "product_id": int(arg)})
            await bot.send_message(chat_id, f"📷 Надішли фото для товару #{arg}:", reply_markup=_wiz_nav_kb())
            return True

        if action == "arch_sku" and arg.isdigit():
            _state_set(tenant_id, chat_id, {"mode": "arch_edit_sku", "product_id": int(arg)})
            await bot.send_message(chat_id, f"🏷 Надішли SKU для товару #{arg} (або `-` щоб очистити):", reply_markup=_wiz_nav_kb())
            return True

        # Categories manage/delete
        if action == "cat_manage":
            _state_clear(tenant_id, chat_id)
            await _send_manage_categories_pick(bot, chat_id, tenant_id)
            return True

        if action == "cat_delete":
            _state_clear(tenant_id, chat_id)
            await _send_delete_categories_pick(bot, chat_id, tenant_id)
            return True

        if action == "cat_open" and arg.isdigit():
            _state_clear(tenant_id, chat_id)
            cid = int(arg)
            _state_set(tenant_id, chat_id, {"mode": "cat_browse", "category_id": cid})
            await _send_admin_category_first_product(bot, chat_id, tenant_id, cid)
            return True

        if action == "cat_del" and arg.isdigit():
            if CategoriesRepo is None:
                await bot.send_message(chat_id, "Категорії не підключені.", reply_markup=_catalog_kb())
                return True
            try:
                await CategoriesRepo.delete(tenant_id, int(arg))  # type: ignore[misc]
                await bot.send_message(chat_id, "✅ Категорію видалено. Товари перенесено в 'Без категорії'.", reply_markup=_catalog_kb())
            except Exception as e:
                await bot.send_message(chat_id, f"❌ Не вдалося видалити: {e}", reply_markup=_catalog_kb())
            return True

        # Products list / enable-disable by ID
        if action == "listp":
            _state_clear(tenant_id, chat_id)
            page = int(arg) if arg.isdigit() else 0
            await _send_products_list_inline(bot, chat_id, tenant_id, page)
            return True

        if action == "p_open" and arg.isdigit():
            _state_clear(tenant_id, chat_id)
            pid = int(arg)
            card = await _build_admin_product_card(tenant_id, pid, 0)
            if not card:
                await bot.send_message(chat_id, "❌ Товар не знайдено або не активний.", reply_markup=_catalog_kb())
                return True
            if card["has_photo"]:
                await bot.send_photo(chat_id, photo=card["file_id"], caption=card["text"], parse_mode="Markdown", reply_markup=card["kb"])
            else:
                await bot.send_message(chat_id, card["text"], parse_mode="Markdown", reply_markup=card["kb"])
            return True

        if action == "disable":
            _state_set(tenant_id, chat_id, {"mode": "disable"})
            await bot.send_message(chat_id, "Надішли ID товару (цифрою), який вимкнути:", reply_markup=_wiz_nav_kb())
            return True

        if action == "enable":
            _state_set(tenant_id, chat_id, {"mode": "enable"})
            await bot.send_message(chat_id, "Надішли ID товару (цифрою), який увімкнути:", reply_markup=_wiz_nav_kb())
            return True

        # Create category
        if action == "cat_create":
            _state_set(tenant_id, chat_id, {"mode": "cat_create_name"})
            await bot.send_message(chat_id, "➕ Введи назву нової категорії:", reply_markup=_wiz_nav_kb())
            return True

        # Wizard create product
        if action == "wiz_start":
            await _wiz_ask_name(bot, chat_id, tenant_id)
            return True

        if action == "wiz_cat":
            st = _state_get(tenant_id, chat_id) or {}
            draft = st.get("draft") or {}
            draft["category_id"] = int(arg) if arg.isdigit() else None
            await _wiz_create_and_go_photos(bot, chat_id, tenant_id, draft)
            return True

        if action == "wiz_skip":
            st = _state_get(tenant_id, chat_id) or {}
            mode = str(st.get("mode") or "")
            draft = st.get("draft") or {}

            if mode == "wiz_sku":
                draft["sku"] = ""
                await _wiz_ask_price(bot, chat_id, tenant_id, draft)
                return True

            if mode == "wiz_desc":
                draft["description"] = ""
                await _wiz_ask_category(bot, chat_id, tenant_id, draft)
                return True

            if mode == "wiz_category":
                default_cid = int(st.get("default_category_id") or 0)
                draft["category_id"] = default_cid if default_cid > 0 else None
                await _wiz_create_and_go_photos(bot, chat_id, tenant_id, draft)
                return True

            return True

        if action == "wiz_done":
            st = _state_get(tenant_id, chat_id) or {}
            product_id = int(st.get("product_id") or 0)
            _state_clear(tenant_id, chat_id)
            if product_id > 0:
                await _wiz_finish(bot, chat_id, product_id)
                return True
            await bot.send_message(chat_id, "✅ Готово.", reply_markup=_admin_home_kb())
            return True

        if action == "wiz_photo_more":
            st = _state_get(tenant_id, chat_id) or {}
            product_id = int(arg) if arg.isdigit() else int(st.get("product_id") or 0)
            if product_id <= 0:
                await bot.send_message(chat_id, "❌ Нема product_id. Відкрий wizard заново.", reply_markup=_admin_home_kb())
                return True
            await _wiz_photos_start(bot, chat_id, tenant_id, product_id)
            return True

        if action == "wiz_desc_edit":
            if not arg.isdigit():
                await bot.send_message(chat_id, "❌ Нема ID товару.", reply_markup=_admin_home_kb())
                return True
            pid = int(arg)
            _state_set(tenant_id, chat_id, {"mode": "desc_edit", "product_id": pid})
            await bot.send_message(chat_id, f"📝 Надішли новий опис для товару #{pid}:", reply_markup=_wiz_nav_kb(allow_skip=True))
            return True

        # Product cards actions (admin + promos)
        if action in ("pc_prev", "pc_next", "p_to_arch", "p_enable", "p_setcat", "pprice", "pname", "p_photo", "psku", "pp_prev", "pp_next"):
            if not (arg.isdigit() and arg2.isdigit()):
                return True

            pid = int(arg)
            cid = int(arg2)
            cat = cid if cid > 0 else None

            if action == "pc_prev":
                p = await ProductsRepo.get_prev_active(tenant_id, pid, category_id=cat)
                if p:
                    await _edit_admin_product_card(bot, chat_id, msg_id, tenant_id, int(p["id"]), cid)
                return True

            if action == "pc_next":
                p = await ProductsRepo.get_next_active(tenant_id, pid, category_id=cat)
                if p:
                    await _edit_admin_product_card(bot, chat_id, msg_id, tenant_id, int(p["id"]), cid)
                return True

            if action == "pp_prev":
                p = await ProductsRepo.get_prev_active(tenant_id, pid, category_id=cat)
                if p:
                    await _edit_promo_product_card(bot, chat_id, msg_id, tenant_id, int(p["id"]), cid)
                return True

            if action == "pp_next":
                p = await ProductsRepo.get_next_active(tenant_id, pid, category_id=cat)
                if p:
                    await _edit_promo_product_card(bot, chat_id, msg_id, tenant_id, int(p["id"]), cid)
                return True

            if action == "p_to_arch":
                await ProductsRepo.set_active(tenant_id, pid, False)
                p2 = await ProductsRepo.get_next_active(tenant_id, pid, category_id=cat)
                if not p2:
                    p2 = await ProductsRepo.get_prev_active(tenant_id, pid, category_id=cat)
                if p2:
                    await _edit_admin_product_card(bot, chat_id, msg_id, tenant_id, int(p2["id"]), cid)
                else:
                    await bot.send_message(chat_id, "✅ Товар перенесено в архів. У цій категорії більше нема активних.", reply_markup=_catalog_kb())
                return True

            if action == "p_enable":
                await ProductsRepo.set_active(tenant_id, pid, True)
                await _edit_admin_product_card(bot, chat_id, msg_id, tenant_id, pid, cid)
                return True

            if action == "p_setcat":
                if CategoriesRepo is None:
                    await bot.send_message(chat_id, "Категорії не підключені.", reply_markup=_catalog_kb())
                    return True
                cats = await CategoriesRepo.list(tenant_id, limit=100)  # type: ignore[misc]
                _state_set(tenant_id, chat_id, {"mode": "p_setcat_pick", "product_id": pid, "back_category_id": cid})
                await bot.send_message(
                    chat_id,
                    "📁 Обери нову категорію:",
                    reply_markup=_category_pick_kb(cats, prefix="tgadm:p_setcat_do", back_to="tgadm:cat_manage"),
                )
                return True

            if action == "pprice":
                _state_set(tenant_id, chat_id, {"mode": "edit_price", "product_id": pid, "category_id": cid})
                await bot.send_message(chat_id, f"💰 Надішли нову ціну для товару #{pid} (1200.50):", reply_markup=_wiz_nav_kb())
                return True

            if action == "pname":
                _state_set(tenant_id, chat_id, {"mode": "edit_name", "product_id": pid, "category_id": cid})
                await bot.send_message(chat_id, f"✏️ Надішли нову назву для товару #{pid}:", reply_markup=_wiz_nav_kb())
                return True

            if action == "p_photo":
                _state_set(tenant_id, chat_id, {"mode": "add_photo_to_pid", "product_id": pid})
                await bot.send_message(chat_id, f"📷 Надішли фото для товару #{pid}:", reply_markup=_wiz_nav_kb())
                return True

            if action == "psku":
                _state_set(tenant_id, chat_id, {"mode": "edit_sku", "product_id": pid, "category_id": cid})
                await bot.send_message(chat_id, f"🏷 Надішли SKU для товару #{pid} (або `-` щоб очистити):", reply_markup=_wiz_nav_kb())
                return True

            return True

        if action == "p_setcat_do" and arg.isdigit():
            st = _state_get(tenant_id, chat_id) or {}
            pid = int(st.get("product_id") or 0)
            back_cid = int(st.get("back_category_id") or 0)
            new_cid = int(arg)
            if pid:
                await ProductsRepo.set_category(tenant_id, pid, new_cid)
                _state_clear(tenant_id, chat_id)
                await bot.send_message(chat_id, "✅ Категорію змінено.", reply_markup=_catalog_kb())
                if back_cid:
                    await _send_admin_category_first_product(bot, chat_id, tenant_id, back_cid)
            return True

        # PROMOS
        if action == "promos":
            _state_clear(tenant_id, chat_id)
            await _send_promos_home(bot, chat_id, tenant_id)
            return True

        if action == "promo_list":
            _state_clear(tenant_id, chat_id)
            page = int(arg) if arg.isdigit() else 0
            await _send_promos_list(bot, chat_id, tenant_id, page)
            return True

        if action == "promo_open" and arg.isdigit():
            _state_clear(tenant_id, chat_id)
            await _send_promo_product_card(bot, chat_id, tenant_id, int(arg), int(arg2) if arg2.isdigit() else 0)
            return True

        if action == "promo_add":
            _state_set(tenant_id, chat_id, {"mode": "promo_pick_id"})
            await bot.send_message(chat_id, "➕ *Нова акція*\n\nВведи ID товару:", parse_mode="Markdown", reply_markup=_wiz_nav_kb())
            return True

        if action == "promo_clear" and arg.isdigit():
            pid = int(arg)
            await ProductsRepo.set_promo(tenant_id, pid, 0, 0)
            await bot.send_message(chat_id, f"✅ Акцію знято з товару #{pid}.", reply_markup=_promos_kb())
            return True

        if action in ("promo_edit", "promo_price") and arg.isdigit():
            pid = int(arg)
            _state_set(tenant_id, chat_id, {"mode": "promo_edit_price", "product_id": pid})
            await bot.send_message(chat_id, f"💸 Введи *ціну акції* для #{pid} (1200.50):", parse_mode="Markdown", reply_markup=_wiz_nav_kb())
            return True

        if action == "promo_until" and arg.isdigit():
            pid = int(arg)
            _state_set(tenant_id, chat_id, {"mode": "promo_edit_until", "product_id": pid})
            await bot.send_message(chat_id, f"⏰ Введи *дату завершення* для #{pid} у форматі `DD.MM.YYYY HH:MM` або `0`:", parse_mode="Markdown", reply_markup=_wiz_nav_kb())
            return True

        if action == "cancel":
            _state_clear(tenant_id, chat_id)
            await bot.send_message(chat_id, "✅ Скасовано.", reply_markup=_admin_home_kb())
            return True

        return False

    # ---------------- messages ----------------
    msg = _extract_message(data)
    if not msg:
        return False

    chat_id = int(msg["chat"]["id"])
    text = (msg.get("text") or "").strip()

    if text in ("/a", "/a_help"):
        await _send_admin_home(bot, chat_id)
        return True

    st = _state_get(tenant_id, chat_id)
    if not st:
        return False

    mode = str(st.get("mode") or "")

    # =========================
    # SUPPORT (admin) message modes
    # =========================
    if mode == "sup_edit_title":
        key = str(st.get("key") or "").strip()
        title = (text or "").strip()
        if not key:
            _state_clear(tenant_id, chat_id)
            return True
        if not title:
            await bot.send_message(chat_id, "Назва не може бути пустою.")
            return True
        await TelegramShopSupportLinksRepo.upsert(tenant_id, key, title=title)
        _state_clear(tenant_id, chat_id)
        await bot.send_message(chat_id, "✅ Назву збережено.", reply_markup=_admin_home_kb())
        return True

    if mode == "sup_edit_url":
        key = str(st.get("key") or "").strip()
        url = (text or "").strip()
        if not key:
            _state_clear(tenant_id, chat_id)
            return True
        await TelegramShopSupportLinksRepo.upsert(tenant_id, key, url=url)
        _state_clear(tenant_id, chat_id)
        await bot.send_message(chat_id, "✅ Значення/URL збережено.", reply_markup=_admin_home_kb())
        return True

    # photo modes
    if mode in ("wiz_photo", "add_photo_to_pid", "arch_add_photo"):
        product_id = int(st.get("product_id") or 0)
        if product_id <= 0:
            _state_clear(tenant_id, chat_id)
            await bot.send_message(chat_id, "❌ Нема product_id в стані.", reply_markup=_admin_home_kb())
            return True

        file_id = _extract_image_file_id(msg)
        if not file_id:
            await bot.send_message(chat_id, "Надішли *фото*.", parse_mode="Markdown", reply_markup=_wiz_nav_kb())
            return True

        await ProductsRepo.add_product_photo(tenant_id, product_id, file_id)

        # ✅ автопост у канал — лише для "нового товару" у wizard і тільки 1 раз
        if mode == "wiz_photo" and not bool(st.get("announced")):
            try:
                await maybe_post_new_product(bot, tenant_id, product_id)
                st["announced"] = True
                _state_set(tenant_id, chat_id, st)  # зберегли прапорець
            except Exception:
                pass

        if mode == "wiz_photo":
            await bot.send_message(
                chat_id,
                f"✅ Фото додано до *#{product_id}*.\nНадсилай ще або натисни *Готово* ✅",
                parse_mode="Markdown",
                reply_markup=_wiz_photos_kb(product_id=product_id),
            )
            return True

        _state_clear(tenant_id, chat_id)
        await bot.send_message(chat_id, f"✅ Фото додано до *#{product_id}*.", parse_mode="Markdown", reply_markup=_catalog_kb())
        return True

    # enable/disable by id
    if mode in ("enable", "disable"):
        if not text.isdigit():
            await bot.send_message(chat_id, "Надішли тільки цифру ID.")
            return True
        pid2 = int(text)
        await ProductsRepo.set_active(tenant_id, pid2, mode == "enable")
        _state_clear(tenant_id, chat_id)
        await bot.send_message(chat_id, f"✅ Товар {pid2} {'увімкнено' if mode=='enable' else 'вимкнено'}.", reply_markup=_admin_home_kb())
        return True

    # create category
    if mode == "cat_create_name":
        name = (text or "").strip()
        if not name:
            await bot.send_message(chat_id, "Назва категорії не може бути пустою.")
            return True

        if CategoriesRepo is None:
            _state_clear(tenant_id, chat_id)
            await bot.send_message(chat_id, "📁 Категорії ще не підключені.", reply_markup=_catalog_kb())
            return True

        await CategoriesRepo.ensure_default(tenant_id)  # type: ignore[misc]
        cid = await CategoriesRepo.create(tenant_id, name[:64])  # type: ignore[misc]
        _state_clear(tenant_id, chat_id)
        await bot.send_message(chat_id, f"✅ Категорію створено: *{name}* (id={cid})", parse_mode="Markdown", reply_markup=_catalog_kb())
        return True

    # wizard steps
    if mode == "wiz_name":
        name = (text or "").strip()
        if not name:
            await bot.send_message(chat_id, "Назва не може бути пустою.")
            return True
        draft = st.get("draft") or {}
        draft["name"] = name[:128]
        await _wiz_ask_sku(bot, chat_id, tenant_id, draft)
        return True

    if mode == "wiz_sku":
        draft = st.get("draft") or {}
        sku = (text or "").strip()
        draft["sku"] = sku[:64] if sku else ""
        await _wiz_ask_price(bot, chat_id, tenant_id, draft)
        return True

    if mode == "wiz_price":
        price_kop = _parse_price_to_kop(text)
        if price_kop is None or price_kop <= 0:
            await bot.send_message(chat_id, "Ціна не розпізнана. Приклад: `1200.50` або `1200`", parse_mode="Markdown")
            return True
        draft = st.get("draft") or {}
        draft["price_kop"] = int(price_kop)
        await _wiz_ask_promo_price(bot, chat_id, tenant_id, draft)
        return True

    if mode == "wiz_promo_price":
        promo_kop = _parse_price_to_kop(text)
        if promo_kop is None or promo_kop <= 0:
            await bot.send_message(
                chat_id,
                "Акційна ціна не розпізнана. Приклад: `999.99` або натисни *Не буде акції*.",
                parse_mode="Markdown",
                reply_markup=_wiz_promo_kb(),
            )
            return True

        draft = st.get("draft") or {}
        base_kop = int(draft.get("price_kop") or 0)

        # щоб акція була дешевша
        if base_kop > 0 and int(promo_kop) >= base_kop:
            await bot.send_message(
                chat_id,
                "Акційна ціна має бути *менша* за звичайну.\n"
                f"Звичайна: `{_fmt_money(base_kop)}`",
                parse_mode="Markdown",
                reply_markup=_wiz_promo_kb(),
            )
            return True

        draft["promo_price_kop"] = int(promo_kop)
        draft["promo_until_ts"] = 0  # при створенні: без кінця (можна потім змінити в Акціях)
        await _wiz_ask_desc(bot, chat_id, tenant_id, draft)
        return True

    if mode == "wiz_desc":
        draft = st.get("draft") or {}
        draft["description"] = (text or "").strip()
        await _wiz_ask_category(bot, chat_id, tenant_id, draft)
        return True

    if mode == "desc_edit":
        product_id = int(st.get("product_id") or 0)
        if not product_id:
            _state_clear(tenant_id, chat_id)
            return True
        await ProductsRepo.set_description(tenant_id, product_id, text)
        _state_clear(tenant_id, chat_id)
        await bot.send_message(chat_id, f"✅ Опис оновлено для #{product_id}.", reply_markup=_catalog_kb())
        return True

    # SKU edits
    if mode == "edit_sku":
        pid = int(st.get("product_id") or 0)
        cid = int(st.get("category_id") or 0)
        raw = (text or "").strip()
        sku = "" if raw in ("-", "0") else raw
        await ProductsRepo.set_sku(tenant_id, pid, sku)  # type: ignore[attr-defined]
        _state_clear(tenant_id, chat_id)
        await bot.send_message(chat_id, "✅ SKU оновлено.", reply_markup=_catalog_kb())
        if cid:
            await _send_admin_category_first_product(bot, chat_id, tenant_id, cid)
        return True

    if mode == "arch_edit_sku":
        pid = int(st.get("product_id") or 0)
        raw = (text or "").strip()
        sku = "" if raw in ("-", "0") else raw
        await ProductsRepo.set_sku(tenant_id, pid, sku)  # type: ignore[attr-defined]
        _state_clear(tenant_id, chat_id)
        await bot.send_message(chat_id, "✅ SKU оновлено.", reply_markup=_catalog_kb())
        return True

    # archive edit name/price
    if mode == "arch_edit_name":
        pid = int(st.get("product_id") or 0)
        nm = (text or "").strip()
        if not nm:
            await bot.send_message(chat_id, "Назва не може бути пустою.")
            return True
        await ProductsRepo.set_name(tenant_id, pid, nm)
        _state_clear(tenant_id, chat_id)
        await bot.send_message(chat_id, "✅ Назву оновлено.", reply_markup=_catalog_kb())
        return True

    if mode == "arch_edit_price":
        pid = int(st.get("product_id") or 0)
        price_kop = _parse_price_to_kop(text)
        if price_kop is None or price_kop <= 0:
            await bot.send_message(chat_id, "Ціна не розпізнана. Приклад: `1200.50` або `1200`", parse_mode="Markdown")
            return True
        await ProductsRepo.set_price_kop(tenant_id, pid, int(price_kop))
        _state_clear(tenant_id, chat_id)
        await bot.send_message(chat_id, "✅ Ціну оновлено.", reply_markup=_catalog_kb())
        return True

    # edit name/price in category manage
    if mode == "edit_price":
        pid = int(st.get("product_id") or 0)
        cid = int(st.get("category_id") or 0)
        price_kop = _parse_price_to_kop(text)
        if price_kop is None or price_kop <= 0:
            await bot.send_message(chat_id, "Ціна не розпізнана. Приклад: `1200.50` або `1200`", parse_mode="Markdown")
            return True
        await ProductsRepo.set_price_kop(tenant_id, pid, int(price_kop))
        _state_clear(tenant_id, chat_id)
        await bot.send_message(chat_id, f"✅ Ціну оновлено для #{pid}.", reply_markup=_catalog_kb())
        if cid:
            await _send_admin_category_first_product(bot, chat_id, tenant_id, cid)
        return True

    if mode == "edit_name":
        pid = int(st.get("product_id") or 0)
        cid = int(st.get("category_id") or 0)
        nm = (text or "").strip()
        if not nm:
            await bot.send_message(chat_id, "Назва не може бути пустою.")
            return True
        await ProductsRepo.set_name(tenant_id, pid, nm)
        _state_clear(tenant_id, chat_id)
        await bot.send_message(chat_id, f"✅ Назву оновлено для #{pid}.", reply_markup=_catalog_kb())
        if cid:
            await _send_admin_category_first_product(bot, chat_id, tenant_id, cid)
        return True

    # PROMOS: wizard (manual add promo by product id)
    if mode == "promo_pick_id":
        if not text.isdigit():
            await bot.send_message(chat_id, "Надішли тільки цифру ID товару.", reply_markup=_wiz_nav_kb())
            return True
        pid = int(text)
        p = await _get_product_any(tenant_id, pid)
        if not p or not bool(p.get("is_active")):
            await bot.send_message(chat_id, "❌ Товар не знайдено або він не активний. Спробуй інший ID.", reply_markup=_wiz_nav_kb())
            return True
        _state_set(tenant_id, chat_id, {"mode": "promo_set_price", "product_id": pid})
        await bot.send_message(chat_id, f"💸 Введи *ціну акції* для #{pid} (1200.50):", parse_mode="Markdown", reply_markup=_wiz_nav_kb())
        return True

    if mode in ("promo_set_price", "promo_edit_price"):
        pid = int(st.get("product_id") or 0)
        price_kop = _parse_price_to_kop(text)
        if price_kop is None or price_kop <= 0:
            await bot.send_message(chat_id, "Ціна не розпізнана. Приклад: `1200.50` або `1200`", parse_mode="Markdown", reply_markup=_wiz_nav_kb())
            return True

        if mode == "promo_set_price":
            _state_set(tenant_id, chat_id, {"mode": "promo_set_until", "product_id": pid, "promo_price_kop": int(price_kop)})
            await bot.send_message(chat_id, "⏰ Введи *дату завершення* у форматі `DD.MM.YYYY HH:MM` або `0`:", parse_mode="Markdown", reply_markup=_wiz_nav_kb())
            return True

        p = await _get_product_any(tenant_id, pid) or {}
        until_ts = int(p.get("promo_until_ts") or 0)
        await ProductsRepo.set_promo(tenant_id, pid, int(price_kop), until_ts)
        _state_clear(tenant_id, chat_id)
        await bot.send_message(chat_id, f"✅ Ціну акції оновлено для #{pid}.", reply_markup=_promos_kb())
        return True

    if mode in ("promo_set_until", "promo_edit_until"):
        pid = int(st.get("product_id") or 0)
        until_ts = _parse_dt_to_ts(text)
        if until_ts is None:
            await bot.send_message(chat_id, "Дата не розпізнана. Формат: `DD.MM.YYYY HH:MM` або `0`", parse_mode="Markdown", reply_markup=_wiz_nav_kb())
            return True

        p = await _get_product_any(tenant_id, pid) or {}
        promo_price = int(st.get("promo_price_kop") or p.get("promo_price_kop") or 0)
        if promo_price <= 0:
            await bot.send_message(chat_id, "Спочатку задай ціну акції.", reply_markup=_wiz_nav_kb())
            return True

        await ProductsRepo.set_promo(tenant_id, pid, promo_price, int(until_ts))
        _state_clear(tenant_id, chat_id)
        await bot.send_message(chat_id, f"✅ Акцію збережено для #{pid}.", reply_markup=_promos_kb())
        return True

    return False