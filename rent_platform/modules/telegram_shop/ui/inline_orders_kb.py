# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

def _kb(rows: list[list[tuple[str, str]]]) -> dict:
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for (t, d) in row] for row in rows]}

def orders_list_kb(order_ids: list[int], *, page: int, has_prev: bool, has_next: bool) -> dict:
    rows: list[list[tuple[str, str]]] = []
    for oid in order_ids:
        rows.append([(f"🧾 Замовлення #{oid}", f"tgord:open:{oid}:{page}")])

    nav: list[tuple[str, str]] = [
        ("⬅️", f"tgord:page:{page-1}:0") if has_prev else ("·", "tgord:noop:0:0"),
        ("➡️", f"tgord:page:{page+1}:0") if has_next else ("·", "tgord:noop:0:0"),
    ]
    rows.append(nav)
    return _kb(rows)

def order_detail_kb(order_id: int, *, page: int, is_archived: bool) -> dict:
    arch_txt = "↩️ Повернути" if is_archived else "🗄 В архів"
    return _kb([
        [("📦 Товари", f"tgord:items:{order_id}:{page}")],
        [(arch_txt, f"tgord:arch:{order_id}:{page}")],
        [("⬅️ Назад до списку", f"tgord:page:{page}:0")],
    ])

def order_items_kb(order_id: int, *, page: int) -> dict:
    return _kb([
        [("⬅️ Назад до замовлення", f"tgord:open:{order_id}:{page}")],
    ])