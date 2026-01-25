from __future__ import annotations
from typing import Any

def _kb(rows: list[list[tuple[str, str]]]) -> dict:
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for (t, d) in row] for row in rows]}


def catalog_categories_kb(categories: list[dict[str, Any]]) -> dict:
    """
    Показує список категорій як кнопки.
    Натиснув категорію -> tgshop:cat:0:<cid>
    """
    rows: list[list[tuple[str, str]]] = []

    # Кнопка "Усі товари"
    rows.append([("🌐 Усі товари", "tgshop:cat:0:0")])

    for c in categories:
        cid = int(c["id"])
        name = str(c["name"])
        rows.append([(f"📁 {name}", f"tgshop:cat:0:{cid}")])

    # назад до каталогу (категорій)
    rows.append([("⬅️ Назад", "tgshop:cats:0:0")])
    return _kb(rows)


def product_card_kb(*, product_id: int, has_prev: bool, has_next: bool, category_id: int | None) -> dict:
    cid = int(category_id or 0)

    nav_row: list[tuple[str, str]] = []
    nav_row.append(("⬅️", f"tgshop:prev:{product_id}:{cid}") if has_prev else ("·", "tgshop:noop:0:0"))
    nav_row.append(("➡️", f"tgshop:next:{product_id}:{cid}") if has_next else ("·", "tgshop:noop:0:0"))

    return _kb([
        nav_row,
        [("🛒 Додати", f"tgshop:add:{product_id}:{cid}"), ("⭐", f"tgshop:fav:{product_id}:{cid}")],
        [("📁 Категорії", "tgshop:cats:0:0")],
    ])