# rent_platform/modules/telegram_shop/ui/inline_orders_kb.py
from __future__ import annotations

import datetime as _dt
from typing import Any


def _kb(rows: list[list[tuple[str, str]]]) -> dict[str, Any]:
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for (t, d) in row] for row in rows]}


def _fmt_money(kop: int) -> str:
    kop = int(kop or 0)
    return f"{kop // 100}.{kop % 100:02d} грн"


def _fmt_dt_short(ts: int) -> str:
    ts = int(ts or 0)
    if ts <= 0:
        return "—"
    return _dt.datetime.fromtimestamp(ts).strftime("%d.%m")


# =========================================================
# Orders list
# =========================================================
def orders_list_kb(
    orders: list[dict[str, Any]],
    *,
    page: int,
    has_prev: bool,
    has_next: bool,
    scope: str,
) -> dict[str, Any]:
    """
    callback_data:
      tgord:list:<page>:<scope>
      tgord:open:<order_id>:<page>:<scope>
      tgord:toggle_scope:<page>:<scope>

    scope: "active" | "arch"
    """
    scope = scope if scope in ("active", "arch") else "active"
    page = max(0, int(page))

    rows: list[list[tuple[str, str]]] = []

    for o in orders or []:
        oid = int(o.get("id") or 0)
        if oid <= 0:
            continue
        created = _fmt_dt_short(int(o.get("created_ts") or 0))
        total = _fmt_money(int(o.get("total_kop") or 0))
        rows.append([(f"📅 {created} • {total}", f"tgord:open:{oid}:{page}:{scope}")])

    nav: list[tuple[str, str]] = []
    nav.append(("⬅️", f"tgord:list:{page - 1}:{scope}") if has_prev else ("·", f"tgord:list:{page}:{scope}"))
    nav.append(("➡️", f"tgord:list:{page + 1}:{scope}") if has_next else ("·", f"tgord:list:{page}:{scope}"))
    rows.append(nav)

    toggle_txt = "🗃 Архів" if scope == "active" else "🧾 Активні"
    rows.append([(toggle_txt, f"tgord:toggle_scope:{page}:{scope}")])

    return _kb(rows)


# =========================================================
# Order detail
# =========================================================
def order_detail_kb(
    order_id: int,
    *,
    is_archived: bool,
    page: int,
    scope: str,
    items_count: int = 0,
) -> dict[str, Any]:
    """
    callback_data:
      tgord:items:<order_id>:<page>:<scope>
      tgord:history:<order_id>:<page>:<scope>
      tgord:arch:<order_id>:<page>:<scope>
      tgord:list:<page>:<scope>
    """
    scope = scope if scope in ("active", "arch") else "active"
    oid = int(order_id)
    page = max(0, int(page))

    arch_txt = "🧾 З архіву" if is_archived else "🗃 В архів"

    return _kb(
        [
            [(f"📦 Товари ({int(items_count or 0)})", f"tgord:items:{oid}:{page}:{scope}")],
            [("📜 Історія статусів", f"tgord:history:{oid}:{page}:{scope}")],
            [(arch_txt, f"tgord:arch:{oid}:{page}:{scope}")],
            [("⬅️ Назад", f"tgord:list:{page}:{scope}")],
        ]
    )


# =========================================================
# Order items list (items as buttons -> open product card)
# =========================================================
def order_items_list_kb(
    order_id: int,
    items: list[dict[str, Any]],
    *,
    page: int,
    scope: str,
) -> dict[str, Any]:
    """
    callback_data:
      tgord:item:<order_id>:<product_id>:<page>:<scope>
      tgord:open:<order_id>:<page>:<scope>
      tgord:list:<page>:<scope>
    """
    scope = scope if scope in ("active", "arch") else "active"
    oid = int(order_id)
    page = max(0, int(page))

    rows: list[list[tuple[str, str]]] = []

    for it in items or []:
        pid = int(it.get("product_id") or 0)
        if pid <= 0:
            continue

        name = str(it.get("name") or f"Товар #{pid}")
        qty = int(it.get("qty") or 0)
        price_kop = int(it.get("price_kop") or 0)
        sum_kop = price_kop * qty

        rows.append([(f"{name} ×{qty} — {_fmt_money(sum_kop)}", f"tgord:item:{oid}:{pid}:{page}:{scope}")])

    rows.append([("⬅️ До замовлення", f"tgord:open:{oid}:{page}:{scope}")])
    rows.append([("⬅️ До списку", f"tgord:list:{page}:{scope}")])

    return _kb(rows)


def order_item_back_kb(order_id: int, *, page: int, scope: str) -> dict[str, Any]:
    scope = scope if scope in ("active", "arch") else "active"
    oid = int(order_id)
    page = max(0, int(page))

    return _kb(
        [
            [("⬅️ До товарів", f"tgord:items:{oid}:{page}:{scope}")],
            [("⬅️ До замовлення", f"tgord:open:{oid}:{page}:{scope}")],
        ]
    )


def order_history_back_kb(order_id: int, *, page: int, scope: str) -> dict[str, Any]:
    scope = scope if scope in ("active", "arch") else "active"
    oid = int(order_id)
    page = max(0, int(page))
    return _kb([[("⬅️ Назад", f"tgord:open:{oid}:{page}:{scope}")]])


# =========================================================
# Backward compatibility
# =========================================================
def order_items_kb(order_id: int, *, page: int, scope: str) -> dict[str, Any]:
    """Старий варіант (якщо десь ще викликається)."""
    scope = scope if scope in ("active", "arch") else "active"
    oid = int(order_id)
    page = max(0, int(page))
    return _kb(
        [
            [("⬅️ До замовлення", f"tgord:open:{oid}:{page}:{scope}")],
            [("⬅️ До списку", f"tgord:list:{page}:{scope}")],
        ]
    )

# Якщо десь був старий “typo”-імпорт — даємо окремий аліас з іншим імʼям (без рекурсії)
def order_item_list_kb(order_id: int, items: list[dict[str, Any]], *, page: int, scope: str) -> dict[str, Any]:
    return order_items_list_kb(order_id, items, page=page, scope=scope)