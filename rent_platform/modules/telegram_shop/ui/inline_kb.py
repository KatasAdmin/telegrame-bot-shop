# -*- coding: utf-8 -*-
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

    # назад до списку категорій
    rows.append([("⬅️ Назад", "tgshop:cats:0:0")])
    return _kb(rows)


def product_card_kb(*, product_id: int, has_prev: bool, has_next: bool, category_id: int | None = None) -> dict:
    """
    Кнопки для картки товару.

    ВАЖЛИВО: category_id має дефолт None, щоб не ламати старі виклики,
    де його ще не передають (у тебе зараз саме так).
    """
    cid = int(category_id or 0)

    nav_row: list[tuple[str, str]] = []
    nav_row.append(("⬅️", f"tgshop:prev:{product_id}:{cid}") if has_prev else ("·", "tgshop:noop:0:0"))
    nav_row.append(("➡️", f"tgshop:next:{product_id}:{cid}") if has_next else ("·", "tgshop:noop:0:0"))

    return _kb(
        [
            nav_row,
            [("🛒 Додати", f"tgshop:add:{product_id}:{cid}"), ("⭐", f"tgshop:fav:{product_id}:{cid}")],
            [("📁 Категорії", "tgshop:cats:0:0")],
        ]
    )


def cart_inline(*, items: list[dict[str, Any]]) -> dict:
    """
    Інлайн-керування кошиком: ➖ qty ➕ 🗑
    Працює з callback:
      tgshop:dec:<product_id>:0
      tgshop:inc:<product_id>:0
      tgshop:del:<product_id>:0
      tgshop:clear:0:0
      tgshop:checkout:0:0
    """
    rows: list[list[tuple[str, str]]] = []

    for it in items:
        pid = int(it.get("product_id") or it.get("id") or 0)
        name = str(it.get("name") or "")
        qty = int(it.get("qty") or 0)
        # одна лінія на товар
        rows.append(
            [
                (f"➖ {name}", f"tgshop:dec:{pid}:0"),
                (f"{qty}", "tgshop:noop:0:0"),
                (f"➕", f"tgshop:inc:{pid}:0"),
                (f"🗑", f"tgshop:del:{pid}:0"),
            ]
        )

    # загальні дії
    rows.append([("🧹 Очистити", "tgshop:clear:0:0"), ("✅ Оформити", "tgshop:checkout:0:0")])
    return _kb(rows)
