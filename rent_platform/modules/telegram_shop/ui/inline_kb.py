from __future__ import annotations

from typing import Any


def _kb(rows: list[list[tuple[str, str]]]) -> dict:
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for (t, d) in row] for row in rows]}


def catalog_categories_kb(categories: list[dict[str, Any]], *, include_all: bool = False) -> dict:
    """
    Кнопки категорій для покупця.

    include_all=False -> НЕ показуємо "Усі товари" (як ти просив).
    Якщо захочеш повернути — передай include_all=True у місці виклику.
    """
    rows: list[list[tuple[str, str]]] = []

    if include_all:
        rows.append([("🌐 Усі товари", "tgshop:cat:0:0")])

    for c in categories:
        cid = int(c["id"])
        name = str(c["name"])
        # можна фільтрувати "Без категорії" або інші системні тут, якщо треба
        rows.append([(f"📁 {name}", f"tgshop:cat:0:{cid}")])

    return _kb(rows)


def product_card_kb(
    *,
    product_id: int,
    has_prev: bool,
    has_next: bool,
    category_id: int | None = None,
) -> dict:
    """
    Кнопки на карточці товару.

    ВАЖЛИВО: для покупця прибрали кнопку "Категорії" (нелогічно в самій картці).
    Повернутись в список категорій покупець може кнопкою "Каталог" (ReplyKeyboard).
    """
    cid = int(category_id or 0)

    nav_row: list[tuple[str, str]] = []
    nav_row.append(("⬅️", f"tgshop:prev:{product_id}:{cid}") if has_prev else ("·", "tgshop:noop:0:0"))
    nav_row.append(("➡️", f"tgshop:next:{product_id}:{cid}") if has_next else ("·", "tgshop:noop:0:0"))

    return _kb([
        nav_row,
        [("🛒 Додати", f"tgshop:add:{product_id}:{cid}"), ("⭐", f"tgshop:fav:{product_id}:{cid}")],
    ])


def cart_inline(items: list[dict[str, Any]]) -> dict:
    """
    Inline керування кошиком (qty ➖ ➕ 🗑).
    callback_data:
      tgshop:dec:<pid>:0
      tgshop:inc:<pid>:0
      tgshop:del:<pid>:0
      tgshop:clear:0:0
      tgshop:checkout:0:0
    """
    rows: list[list[tuple[str, str]]] = []
    for it in items:
        pid = int(it["product_id"])
        qty = int(it["qty"])
        rows.append([
            ("➖", f"tgshop:dec:{pid}:0"),
            (f"{qty}", "tgshop:noop:0:0"),
            ("➕", f"tgshop:inc:{pid}:0"),
            ("🗑", f"tgshop:del:{pid}:0"),
        ])
    rows.append([("🧹 Очистити", "tgshop:clear:0:0"), ("✅ Оформити", "tgshop:checkout:0:0")])
    return _kb(rows)