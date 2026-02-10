# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from typing import Any

from aiogram import Bot
from aiogram.types import InputMediaPhoto

from rent_platform.db.session import db_fetch_all, db_fetch_one, db_execute
from rent_platform.modules.telegram_shop.admin_orders import admin_orders_handle_update
from rent_platform.modules.telegram_shop.channel_announce import maybe_post_new_product
from rent_platform.modules.telegram_shop.repo.products import ProductsRepo
from rent_platform.modules.telegram_shop.repo.support_links import TelegramShopSupportLinksRepo
from rent_platform.modules.telegram_shop.ui.user_kb import BTN_ADMIN, BTN_ADMIN_ORDERS

# CategoriesRepo optional (if file exists)
try:
    from rent_platform.modules.telegram_shop.repo.categories import CategoriesRepo  # type: ignore
except Exception:  # pragma: no cover
    CategoriesRepo = None  # type: ignore


# ============================================================
# In-memory state
# ============================================================
_STATE: dict[tuple[str, int], dict[str, Any]] = {}
_SUP_MENU_MSG_ID: dict[tuple[str, int], int] = {}


# ============================================================
# Public helpers (imported by router)
# ============================================================
def admin_has_state(tenant_id: str, chat_id: int) -> bool:
    return (tenant_id, chat_id) in _STATE


def is_admin_user(*, tenant: dict, user_id: int) -> bool:
    """
    Flexible admin check.
    Supports:
      - tenant["owner_user_id"]
      - tenant["admin_user_ids"] as list[int] / "1,2,3"
      - tenant["admins"] as list[int]
    """
    try:
        uid = int(user_id)
    except Exception:
        return False

    owner = tenant.get("owner_user_id")
    try:
        if owner is not None and int(owner) == uid:
            return True
    except Exception:
        pass

    for k in ("admin_user_ids", "admins"):
        v = tenant.get(k)
        if not v:
            continue

        if isinstance(v, (list, tuple, set)):
            try:
                return uid in {int(x) for x in v}
            except Exception:
                continue

        if isinstance(v, str):
            try:
                ids = {int(x.strip()) for x in v.split(",") if x.strip().isdigit()}
                if uid in ids:
                    return True
            except Exception:
                continue

    return False


# ============================================================
# Utils
# ============================================================
def _now() -> int:
    return int(time.time())


def _kb(rows: list[list[tuple[str, str]]]) -> dict:
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for (t, d) in row] for row in rows]}


def _extract_message(data: dict[str, Any]) -> dict | None:
    return data.get("message") or data.get("edited_message")


def _extract_callback(data: dict[str, Any]) -> dict | None:
    return data.get("callback_query")


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


def _fmt_money(kop: int) -> str:
    kop = int(kop or 0)
    return f"{kop // 100}.{kop % 100:02d} грн"


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
    # heuristic: if <= 200000 assume грн
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


async def _send_or_edit(
    bot: Bot,
    *,
    chat_id: int,
    text: str,
    message_id: int | None,
    reply_markup: Any | None = None,
    parse_mode: str | None = "Markdown",
) -> int:
    """
    Returns message_id of the final message.
    """
    if message_id:
        try:
            await bot.edit_message_text(
                text,
                chat_id=chat_id,
                message_id=int(message_id),
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
            )
            return int(message_id)
        except Exception:
            pass

    m = await bot.send_message(
        chat_id,
        text,
        parse_mode=parse_mode,
        reply_markup=reply_markup,
        disable_web_page_preview=True,
    )
    return int(m.message_id)


# ============================================================
# Menus
# ============================================================
def _admin_home_kb() -> dict:
    return _kb(
        [
            [("📦 Каталог", "tgadm:catalog")],
            [("🧾 Замовлення", "tgadm:ord_menu:0")],
            [("⚙️ Інтеграції", "tgadm:integrations")],  # <-- NEW
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

    nav: list[tuple[str, str]] = [
        ("⬅️", f"tgadm:promo_list:{page-1}:0") if page > 0 else ("·", "tgadm:noop"),
        ("➡️", f"tgadm:promo_list:{page+1}:0") if has_next else ("·", "tgadm:noop"),
    ]
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

    nav: list[tuple[str, str]] = [
        ("⬅️", f"tgadm:listp:{page-1}:0") if page > 0 else ("·", "tgadm:noop"),
        ("➡️", f"tgadm:listp:{page+1}:0") if has_next else ("·", "tgadm:noop"),
    ]
    rows.append(nav)
    rows.append([("⬅️ Назад", "tgadm:prod_menu")])
    return _kb(rows)


def _promo_product_card_kb(*, product_id: int, category_id: int, has_prev: bool, has_next: bool, promo_active: bool) -> dict:
    cid = int(category_id)
    nav_row: list[tuple[str, str]] = [
        ("⬅️", f"tgadm:pp_prev:{product_id}:{cid}") if has_prev else ("·", "tgadm:noop"),
        ("➡️", f"tgadm:pp_next:{product_id}:{cid}") if has_next else ("·", "tgadm:noop"),
    ]
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
    return _kb([[("🚫 Не буде акції", "tgadm:wiz_no_promo")], [("❌ Скасувати", "tgadm:cancel")]])


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
    nav_row: list[tuple[str, str]] = [
        ("⬅️", f"tgadm:pc_prev:{product_id}:{cid}") if has_prev else ("·", "tgadm:noop"),
        ("➡️", f"tgadm:pc_next:{product_id}:{cid}") if has_next else ("·", "tgadm:noop"),
    ]
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

    nav: list[tuple[str, str]] = [
        ("⬅️", f"tgadm:archive:{page-1}") if page > 0 else ("·", "tgadm:noop"),
        ("➡️", f"tgadm:archive:{page+1}") if has_next else ("·", "tgadm:noop"),
    ]
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
# SUPPORT (admin)  ✅ NO MARKDOWN HERE (prevents entity errors)
# ============================================================
_SUPPORT_HINTS: dict[str, str] = {
    "support_channel": "Введи @username каналу або посилання.\nПриклад: https://t.me/your_channel",
    "support_chat": "Введи chat_id (краще) або @username або посилання.\nПриклад chat_id: -1001234567890",
    "support_site": "Введи посилання на сайт.\nПриклад: https://example.com",
    "support_manager": "Введи @username менеджера або телефон.\nПриклад: @manager_name",
    "support_email": "Введи email.\nПриклад: hello@example.com",
    "announce_chat_id": "Введи chat_id каналу для автопосту новинок.\nПриклад: -1001234567890",
}


def _sup_short(v: str, n: int = 18) -> str:
    v = (v or "").strip()
    if not v:
        return "—"
    if len(v) <= n:
        return v
    return v[: n - 1] + "…"


def _sup_admin_kb(items: list[dict[str, Any]]) -> dict:
    rows: list[list[tuple[str, str]]] = []
    for it in items:
        key = str(it.get("key") or "")
        title = str(it.get("title") or key)
        enabled = bool(it.get("enabled"))
        url = str(it.get("url") or "")

        icon = "✅" if enabled else "⛔"
        rows.append(
            [
                (_safe_btn(f"{icon} {title}", 40), f"tgadm:sup_toggle:{key}"),
                (_safe_btn(f"✏️ {_sup_short(url)}", 25), f"tgadm:sup_edit:{key}"),
            ]
        )

    rows.append([("⬅️ В адмін-меню", "tgadm:home")])
    return _kb(rows)


async def _send_support_admin_menu(bot: Bot, chat_id: int, tenant_id: str, *, edit_message_id: int | None = None) -> int:
    await TelegramShopSupportLinksRepo.ensure_defaults(tenant_id)
    items = await TelegramShopSupportLinksRepo.list_all(tenant_id)

    text = (
        "🆘 Підтримка — налаштування\n\n"
        "• Тап по назві: увімк/вимк кнопку\n"
        "• ✏️: встановити значення (chat_id / @username / URL / email)\n\n"
        "Автопост новинок: увімкни 'Автопост новинок (канал)' і вкажи announce_chat_id.\n"
        "Формат chat_id: -1001234567890"
    )
    kb = _sup_admin_kb(items)

    # IMPORTANT: parse_mode=None avoids Telegram markdown entity errors for values with "_" etc.
    mid = await _send_or_edit(
        bot,
        chat_id=chat_id,
        text=text,
        message_id=edit_message_id,
        reply_markup=kb,
        parse_mode=None,
    )
    return int(mid)


async def _send_support_edit_prompt(bot: Bot, chat_id: int, tenant_id: str, key: str) -> None:
    it = await TelegramShopSupportLinksRepo.get(tenant_id, key) or {}
    title = str(it.get("title") or key)
    cur = str(it.get("url") or "")

    hint = _SUPPORT_HINTS.get(key, "Введи значення одним повідомленням.")
    await bot.send_message(
        chat_id,
        "✏️ Зміна значення\n\n"
        f"Пункт: {title}\n"
        f"Ключ: {key}\n"
        f"Поточне: {cur if cur else '—'}\n\n"
        f"{hint}\n\n"
        "Скасувати: /cancel",
        parse_mode=None,  # ✅
        reply_markup=_kb([[("❌ Скасувати", "tgadm:cancel")]]),
        disable_web_page_preview=True,
    )


# ============================================================
# Senders
# ============================================================
async def _send_admin_home(bot: Bot, chat_id: int, *, edit_message_id: int | None = None) -> None:
    await _send_or_edit(
        bot,
        chat_id=chat_id,
        message_id=edit_message_id,
        text="🛠 *Адмінка магазину*\n\nОдна точка входу — *📦 Каталог* 👇",
        reply_markup=_admin_home_kb(),
        parse_mode="Markdown",
    )


async def _send_catalog_home(bot: Bot, chat_id: int, *, edit_message_id: int | None = None) -> None:
    await _send_or_edit(
        bot,
        chat_id=chat_id,
        message_id=edit_message_id,
        text="📦 *Каталог*\n\nОбери розділ 👇",
        reply_markup=_catalog_kb(),
        parse_mode="Markdown",
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
        disable_web_page_preview=True,
    )


# ============================================================
# Products paging (SQL, no heavy list+sort)
# ============================================================
async def _list_active_products_page(tenant_id: str, *, page: int, page_size: int = 12) -> tuple[list[dict[str, Any]], bool]:
    page = max(0, int(page))
    off = page * page_size

    q = """
    SELECT id, name, COALESCE(sku,'') AS sku, COALESCE(price_kop,0) AS price_kop
    FROM telegram_shop_products
    WHERE tenant_id = :tid AND is_active = true
    ORDER BY id DESC
    LIMIT :lim OFFSET :off
    """
    rows = await db_fetch_all(q, {"tid": tenant_id, "lim": int(page_size) + 1, "off": int(off)}) or []
    has_next = len(rows) > page_size
    return (rows[:page_size], bool(has_next))

# ============================================================
# Products list / cards / promos / archive
# ============================================================
async def _send_products_list_inline(bot: Bot, chat_id: int, tenant_id: str, page: int) -> None:
    page = max(0, int(page))
    chunk, has_next = await _list_active_products_page(tenant_id, page=page, page_size=12)

    if not chunk:
        await bot.send_message(chat_id, "Поки що немає активних товарів.", reply_markup=_catalog_kb())
        return

    await bot.send_message(
        chat_id,
        "📦 *Активні товари*\n\nНатисни товар 👇",
        parse_mode="Markdown",
        reply_markup=_products_list_kb(chunk, page=page, has_next=has_next),
        disable_web_page_preview=True,
    )


async def _send_promos_home(bot: Bot, chat_id: int, tenant_id: str) -> None:
    now = _now()
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
        disable_web_page_preview=True,
    )


async def _send_promos_list(bot: Bot, chat_id: int, tenant_id: str, page: int) -> None:
    now = _now()
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
        disable_web_page_preview=True,
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

    now = _now()
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
        await bot.send_photo(
            chat_id,
            photo=card["file_id"],
            caption=card["text"],
            parse_mode="Markdown",
            reply_markup=card["kb"],
        )
    else:
        await bot.send_message(
            chat_id,
            card["text"],
            parse_mode="Markdown",
            reply_markup=card["kb"],
            disable_web_page_preview=True,
        )


async def _edit_promo_product_card(bot: Bot, chat_id: int, message_id: int, tenant_id: str, product_id: int, category_id: int | None) -> bool:
    card = await _build_promo_product_card(tenant_id, int(product_id), category_id)
    if not card:
        return False

    try:
        if card["has_photo"]:
            media = InputMediaPhoto(media=card["file_id"], caption=card["text"], parse_mode="Markdown")
            await bot.edit_message_media(media=media, chat_id=chat_id, message_id=message_id, reply_markup=card["kb"])
        else:
            await bot.edit_message_text(
                card["text"],
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="Markdown",
                reply_markup=card["kb"],
                disable_web_page_preview=True,
            )
        return True
    except Exception:
        return False


# ============================================================
# Archive
# ============================================================
async def _send_archive(bot: Bot, chat_id: int, tenant_id: str, page: int) -> None:
    page = max(0, int(page))
    limit = 12
    offset = page * limit

    q = """
    SELECT id, name, COALESCE(sku,'') AS sku, COALESCE(price_kop,0) AS price_kop
    FROM telegram_shop_products
    WHERE tenant_id = :tid AND is_active = false
    ORDER BY id DESC
    LIMIT :lim OFFSET :off
    """
    rows = await db_fetch_all(q, {"tid": tenant_id, "lim": int(limit) + 1, "off": int(offset)}) or []
    has_next = len(rows) > limit
    chunk = rows[:limit]

    if not chunk:
        await bot.send_message(chat_id, "🗃 Архів порожній (вимкнених товарів нема).", reply_markup=_catalog_kb())
        return

    await bot.send_message(
        chat_id,
        "🗃 *Архів (вимкнені)*\n\nНатисни товар 👇",
        parse_mode="Markdown",
        reply_markup=_archive_list_kb(chunk, page=page, has_next=bool(has_next)),
        disable_web_page_preview=True,
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
        await bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=kb, disable_web_page_preview=True)


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
        disable_web_page_preview=True,
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
        disable_web_page_preview=True,
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
        await bot.send_message(chat_id, card["text"], parse_mode="Markdown", reply_markup=card["kb"], disable_web_page_preview=True)


async def _edit_admin_product_card(bot: Bot, chat_id: int, message_id: int, tenant_id: str, product_id: int, category_id: int | None) -> bool:
    card = await _build_admin_product_card(tenant_id, product_id, category_id)
    if not card:
        return False

    try:
        if card["has_photo"]:
            media = InputMediaPhoto(media=card["file_id"], caption=card["text"], parse_mode="Markdown")
            await bot.edit_message_media(media=media, chat_id=chat_id, message_id=message_id, reply_markup=card["kb"])
        else:
            await bot.edit_message_text(
                card["text"],
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="Markdown",
                reply_markup=card["kb"],
                disable_web_page_preview=True,
            )
        return True
    except Exception:
        return False


# ============================================================
# Integrations (admin-only, hidden from user menus)
# ============================================================
async def _send_integrations_home(bot: Bot, chat_id: int) -> None:
    # parse_mode=None to avoid any entity issues (keys/urls)
    text = (
        "⚙️ Інтеграції\n\n"
        "Тут будемо підключати зовнішні сервіси (1C/сайт/оплати/склади).\n"
        "Поки що це меню-заглушка.\n\n"
        "• Автопост новинок — налаштовується в Підтримка (announce_chat_id)\n"
    )
    await bot.send_message(chat_id, text, parse_mode=None, reply_markup=_kb([[("⬅️ В адмін-меню", "tgadm:home")]]))


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
        disable_web_page_preview=True,
    )


async def _wiz_ask_sku(bot: Bot, chat_id: int, tenant_id: str, draft: dict) -> None:
    _state_set(tenant_id, chat_id, {"mode": "wiz_sku", "draft": draft})
    await bot.send_message(
        chat_id,
        "2/6 Введи *SKU/артикул* (або натисни `Пропустити`):",
        parse_mode="Markdown",
        reply_markup=_wiz_nav_kb(allow_skip=True),
        disable_web_page_preview=True,
    )


async def _wiz_ask_price(bot: Bot, chat_id: int, tenant_id: str, draft: dict) -> None:
    _state_set(tenant_id, chat_id, {"mode": "wiz_price", "draft": draft})
    await bot.send_message(
        chat_id,
        "3/6 Введи *ціну* (наприклад `1200.50` або `1200`):",
        parse_mode="Markdown",
        reply_markup=_wiz_nav_kb(),
        disable_web_page_preview=True,
    )


async def _wiz_ask_promo_price(bot: Bot, chat_id: int, tenant_id: str, draft: dict) -> None:
    _state_set(tenant_id, chat_id, {"mode": "wiz_promo_price", "draft": draft})
    await bot.send_message(
        chat_id,
        "4/6 *Акційна ціна*\n\nВведи *акційну ціну* (наприклад `999.99`) або натисни кнопку нижче 👇",
        parse_mode="Markdown",
        reply_markup=_wiz_promo_kb(),
        disable_web_page_preview=True,
    )


async def _wiz_ask_desc(bot: Bot, chat_id: int, tenant_id: str, draft: dict) -> None:
    _state_set(tenant_id, chat_id, {"mode": "wiz_desc", "draft": draft})
    await bot.send_message(
        chat_id,
        "5/6 Додай *опис* (або натисни `Пропустити`):",
        parse_mode="Markdown",
        reply_markup=_wiz_nav_kb(allow_skip=True),
        disable_web_page_preview=True,
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
        disable_web_page_preview=True,
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
        disable_web_page_preview=True,
    )


async def _wiz_finish(bot: Bot, chat_id: int, product_id: int) -> None:
    await bot.send_message(
        chat_id,
        f"✅ *Готово!* Товар *#{product_id}* створено.\n\nМожеш додати фото/опис або створити ще.",
        parse_mode="Markdown",
        reply_markup=_wiz_finish_kb(product_id=product_id),
        disable_web_page_preview=True,
    )


# ============================================================
# Main entry
# ============================================================
async def handle_update(*, tenant: dict, data: dict[str, Any], bot: Bot) -> bool:
    tenant_id = str(tenant["id"])

    # ---------------- callbacks ----------------
    cb = _extract_cal