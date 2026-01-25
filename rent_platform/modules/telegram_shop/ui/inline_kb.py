from __future__ import annotations

from typing import Any


def _kb(rows: list[list[tuple[str, str]]]) -> dict:
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for (t, d) in row] for row in rows]}


def catalog_categories_kb(
    categories: list[dict[str, Any]],
    *,
    include_all: bool = False,
) -> dict:
    """
    Inline-кнопки категорій для покупця.

    include_all:
      True  -> показує кнопку "🌐 Усі товари"
      False -> ховає її (за замовчуванням, як ти просив)

    ВАЖЛИВО:
    - системні категорії з іменами "__..." ми тут ігноруємо
    - "Без категорії" буде показуватись тільки якщо ти її зробив видимою (repo.categories.sort >= 0),
      бо в роутері ми беремо CategoriesRepo.list_public().
    """
    rows: list[list[tuple[str, str]]] = []

    if include_all:
        rows.append([("🌐 Усі товари", "tgshop:cat:0:0")])

    for c in categories:
        name = str(c.get("name") or "")
        if not name:
            continue
        if name.startswith("__"):
            continue

        cid = int(c["id"])
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
    Inline на картці товару (покупець).

    Повернення в список категорій/каталог:
    - не робимо кнопки "Категорії" тут (ти просив),
      користувач повертається через ReplyKeyboard кнопку "🛍 Каталог".
    """
    cid = int(category_id or 0)

    nav_row: list[tuple[str, str]] = [
        ("⬅️", f"tgshop:prev:{product_id}:{cid}") if has_prev else ("·", "tgshop:noop:0:0"),
        ("➡️", f"tgshop:next:{product_id}:{cid}") if has_next else ("·", "tgshop:noop:0:0"),
    ]

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
