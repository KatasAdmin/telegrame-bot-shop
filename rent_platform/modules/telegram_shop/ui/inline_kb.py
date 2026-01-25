from __future__ import annotations

from typing import Any


def _kb(rows: list[list[tuple[str, str]]]) -> dict[str, Any]:
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for (t, d) in row] for row in rows]}


def catalog_categories_kb(categories: list[dict]) -> dict[str, Any]:
    rows: list[list[tuple[str, str]]] = []
    for c in categories:
        cid = int(c["id"])
        name = str(c["name"])
        rows.append([(f"📁 {name}", f"tgshop:cat:0:{cid}")])
    rows.append([("🛍 Усі товари", "tgshop:cat:0:0")])
    return _kb(rows)


def product_card_kb(*, product_id: int, has_prev: bool, has_next: bool, category_id: int | None = None) -> dict[str, Any]:
    cid = int(category_id) if category_id is not None else 0
    row1: list[tuple[str, str]] = []
    row1.append(("⬅️", f"tgshop:prev:{product_id}:{cid}") if has_prev else ("•", "tgshop:noop:0:0"))
    row1.append(("➡️", f"tgshop:next:{product_id}:{cid}") if has_next else ("•", "tgshop:noop:0:0"))

    row2: list[tuple[str, str]] = [
        ("🛒 Додати", f"tgshop:add:{product_id}:{cid}"),
        ("⭐", f"tgshop:fav:{product_id}:{cid}"),
    ]
    row3: list[tuple[str, str]] = [
        ("📁 Категорії", "tgshop:cats:0:0"),
    ]
    return _kb([row1, row2, row3])


def cart_inline(items: list[dict]) -> dict[str, Any]:
    rows: list[list[tuple[str, str]]] = []
    for it in items:
        pid = int(it["product_id"])
        qty = int(it["qty"])
        name = str(it["name"])
        rows.append(
            [
                (f"➖", f"tgshop:dec:{pid}:0"),
                (f"{qty} × {name}", "tgshop:noop:0:0"),
                (f"➕", f"tgshop:inc:{pid}:0"),
                (f"🗑", f"tgshop:del:{pid}:0"),
            ]
        )
    rows.append([("🧹 Очистити", "tgshop:clear:0:0"), ("✅ Оформити", "tgshop:checkout:0:0")])
    return _kb(rows)