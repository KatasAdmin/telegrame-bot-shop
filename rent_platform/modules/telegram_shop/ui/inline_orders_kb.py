from __future__ import annotations


def _kb(rows: list[list[tuple[str, str]]]) -> dict:
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for (t, d) in row] for row in rows]}


def orders_list_kb(
    order_ids: list[int],
    *,
    page: int,
    has_prev: bool,
    has_next: bool,
    archived: bool = False,
) -> dict:
    """
    Список замовлень + пагінація + кнопка Архів/Історія
    """
    rows: list[list[tuple[str, str]]] = []

    # кнопки відкриття кожного замовлення
    for oid in order_ids:
        rows.append([(f"🧾 Замовлення #{int(oid)}", f"tgord:open:{int(oid)}")])

    # пагінація
    nav: list[tuple[str, str]] = []
    if has_prev:
        nav.append(("⬅️", f"tgord:{'alist' if archived else 'list'}:{max(page - 1, 0)}"))
    if has_next:
        nav.append(("➡️", f"tgord:{'alist' if archived else 'list'}:{page + 1}"))
    if nav:
        rows.append(nav)

    # перемикач архів/історія
    if archived:
        rows.append([("🧾 Історія", "tgord:list:0")])
    else:
        rows.append([("🗄 Архів", "tgord:alist:0")])

    return _kb(rows)


def order_detail_kb(order_id: int, *, is_archived: bool) -> dict:
    """
    Деталка: товари + архів toggle + назад (в історію)
    """
    oid = int(order_id)
    arch_txt = "🗄 Повернути" if is_archived else "🗄 В архів"
    rows = [
        [("📦 Товари", f"tgord:items:{oid}")],
        [(arch_txt, f"tgord:arch:{oid}")],
        [("⬅️ Назад", "tgord:list:0")],
    ]
    return _kb(rows)


def order_items_kb(order_id: int) -> dict:
    """
    З товарів назад у деталку
    """
    oid = int(order_id)
    rows = [
        [("⬅️ Назад", f"tgord:open:{oid}")],
    ]
    return _kb(rows)