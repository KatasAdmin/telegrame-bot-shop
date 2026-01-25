from __future__ import annotations

from typing import Any


def _kb(rows: list[list[tuple[str, str]]]) -> dict:
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for (t, d) in row] for row in rows]}


# -----------------------------
# Catalog categories (for USER)
# -----------------------------
def catalog_categories_kb(categories: list[dict[str, Any]]) -> dict:
    """
    Показує список категорій як кнопки.
    Натиснув категорію -> tgshop:cat:0:<cid>
    (cid=0 означає "Усі товари")
    """
    rows: list[list[tuple[str, str]]] = []

    # "Усі товари"
    rows.append([("🌐 Усі товари", "tgshop:cat:0:0")])

    for c in categories:
        cid = int(c["id"])
        name = str(c["name"])
        rows.append([(f"📁 {name}", f"tgshop:cat:0:{cid}")])

    return _kb(rows)


# -----------------------------
# Product card keyboard (for USER)
# -----------------------------
def product_card_kb(*, product_id: int, has_prev: bool, has_next: bool, category_id: int | None = None) -> dict:
    """
    category_id — щоб листати в межах вибраної категорії.
    Якщо None / 0 — листаємо по всіх товарах.
    """
    cid = int(category_id or 0)

    nav_row: list[tuple[str, str]] = [
        ("⬅️", f"tgshop:prev:{product_id}:{cid}") if has_prev else ("·", "tgshop:noop:0:0"),
        ("➡️", f"tgshop:next:{product_id}:{cid}") if has_next else ("·", "tgshop:noop:0:0"),
    ]

    # ВАЖЛИВО: для покупця НЕ показуємо кнопку "Категорії" на картці.
    # Категорії відкриваються через кнопку 🛍 Каталог (reply keyboard).
    return _kb([
        nav_row,
        [("🛒 Додати", f"tgshop:add:{product_id}:{cid}"), ("⭐", f"tgshop:fav:{product_id}:{cid}")],
    ])


# -----------------------------
# Cart inline controls (for USER)
# -----------------------------
def cart_inline(*, items: list[dict[str, Any]]) -> dict:
    """
    Мінімалістичний UI кошика:
      ➖ qty ➕  🗑
    + кнопки: Оформити / Очистити
    """
    rows: list[list[tuple[str, str]]] = []

    for it in items:
        pid = int(it["product_id"])
        qty = int(it.get("qty") or 0)

        rows.append([
            ("➖", f"tgshop:dec:{pid}:0"),
            (f"{qty}", "tgshop:noop:0:0"),
            ("➕", f"tgshop:inc:{pid}:0"),
            ("🗑", f"tgshop:del:{pid}:0"),
        ])

    rows.append([("✅ Оформити", "tgshop:checkout:0:0"), ("🧹 Очистити", "tgshop:clear:0:0")])
    return _kb(rows)
