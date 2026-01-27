from __future__ import annotations

from typing import Any


def _kb(rows: list[list[tuple[str, str]]]) -> dict[str, Any]:
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for (t, d) in row] for row in rows]}


def orders_list_kb(
    order_ids: list[int],
    *,
    page: int,
    has_prev: bool,
    has_next: bool,
    scope: str,
) -> dict:
    """
    Список замовлень + пагінація + перемикач Активні/Архів.

    callback_data:
      tgord:list:<page>:<scope>
      tgord:open:<order_id>:<page>:<scope>
      tgord:toggle_scope:<page>:<scope>

    scope: "active" | "arch"
    """
    scope = scope if scope in ("active", "arch") else "active"
    page = max(0, int(page))

    rows: list[list[tuple[str, str]]] = []

    # кнопки відкриття кожного замовлення (макс 10 приходить з user_orders.py)
    for oid in order_ids:
        oid_i = int(oid)
        rows.append([(f"🧾 Замовлення #{oid_i}", f"tgord:open:{oid_i}:{page}:{scope}")])

    # пагінація (завжди додаємо рядок, навіть якщо одна сторінка — буде стабільний UX)
    nav: list[tuple[str, str]] = []
    nav.append(("⬅️", f"tgord:list:{page - 1}:{scope}") if has_prev else ("·", f"tgord:list:{page}:{scope}"))
    nav.append(("➡️", f"tgord:list:{page + 1}:{scope}") if has_next else ("·", f"tgord:list:{page}:{scope}"))
    rows.append(nav)

    # перемикач архів/активні
    toggle_txt = "🗃 Архів" if scope == "active" else "🧾 Активні"
    rows.append([(toggle_txt, f"tgord:toggle_scope:{page}:{scope}")])

    return _kb(rows)


def order_detail_kb(
    order_id: int,
    *,
    is_archived: bool,
    page: int,
    scope: str,
) -> dict:
    """
    Деталка: товари + архів toggle + назад (на ту ж сторінку списку).

    callback_data:
      tgord:items:<order_id>:<page>:<scope>
      tgord:arch:<order_id>:<page>:<scope>
      tgord:list:<page>:<scope>
    """
    scope = scope if scope in ("active", "arch") else "active"
    oid = int(order_id)
    page = max(0, int(page))

    arch_txt = "🧾 З архіву" if is_archived else "🗃 В архів"

    return _kb(
        [
            [("📦 Товари", f"tgord:items:{oid}:{page}:{scope}")],
            [(arch_txt, f"tgord:arch:{oid}:{page}:{scope}")],
            [("⬅️ Назад", f"tgord:list:{page}:{scope}")],
        ]
    )


def order_items_kb(order_id: int, *, page: int, scope: str) -> dict:
    """
    З товарів назад у деталку / список.
    """
    scope = scope if scope in ("active", "arch") else "active"
    oid = int(order_id)
    page = max(0, int(page))

    return _kb(
        [
            [("⬅️ До замовлення", f"tgord:open:{oid}:{page}:{scope}")],
            [("⬅️ До списку", f"tgord:list:{page}:{scope}")],
        ]
    )


# Backward-compat alias (старий імпорт у user_orders.py)
def order_items_list_kb(order_id: int, items: list[dict[str, Any]], *, page: int, scope: str) -> dict:
    return order_items_list_kb(order_id, items, page=page, scope=scope)