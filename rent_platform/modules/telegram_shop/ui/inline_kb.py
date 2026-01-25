from __future__ import annotations

from typing import Any


def _kb(rows: list[list[tuple[str, str]]]) -> dict:
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for (t, d) in row] for row in rows]}


def catalog_categories_kb(categories: list[dict[str, Any]], *, include_all: bool = False) -> dict:
    """
    Кнопки категорій для покупця.

    include_all керується адмінкою (кнопка "🌐 Усі товари"):
      - True  => показуємо кнопку "Усі товари" (cat:0)
      - False => тільки список категорій
    """
    rows: list[list[tuple[str, str]]] = []

    if include_all:
        rows.append([("🌐 Усі товари", "tgshop:cat:0:0")])

    for c in categories:
        cid = int(c["id"])
        name = str(c.get("name") or "")
        # categoriesRepo.list_public вже не дає системні, але перестрахуємось
        if name.startswith("__"):
            continue
        rows.append([(f"📁 {name}", f"tgshop:cat:0:{cid}")])

    # якщо взагалі нема категорій, але include_all=True — кнопка буде
    # якщо нема ні категорій, ні include_all — тоді роутер покаже fallback текст
    return _kb(rows)


def product_card_kb(
    *,
    product_id: int,
    has_prev: bool,
    has_next: bool,
    category_id: int | None = None,
) -> dict:
    """
    Кнопки на карточці товару (покупець).

    category_id прошиваємо в callback, щоб prev/next ходили всередині категорії.
    Якщо category_id=None => cid=0 => показуємо "всі товари".
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
    Інлайн керування кошиком.
    ВАЖЛИВО: кошик не залежить від категорій, тому cid=0.
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

    rows.append([("🧹 Очистити", "tgshop:clear:0:0"), ("✅ Оформити", "tgshop:checkout:0:0")])
    return _kb(rows)