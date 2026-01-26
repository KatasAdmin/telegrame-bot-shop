# -*- coding: utf-8 -*-
from __future__ import annotations

def _kb(rows: list[list[tuple[str, str]]]) -> dict:
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for (t, d) in row] for row in rows]}

def orders_list_kb(order_ids: list[int]) -> dict:
    rows: list[list[tuple[str, str]]] = []
    for oid in order_ids:
        rows.append([(f"🧾 Замовлення #{oid}", f"tgord:open:{oid}:0")])
    return _kb(rows)

def order_detail_kb(order_id: int, *, is_archived: bool) -> dict:
    arch_txt = "↩️ Повернути з архіву" if is_archived else "🗄 В архів"
    return _kb([
        [("📦 Товари", f"tgord:items:{order_id}:0")],
        [(arch_txt, f"tgord:arch:{order_id}:0")],
        [("⬅️ Назад", "tgord:list:0:0")],
    ])

def order_items_kb(order_id: int) -> dict:
    return _kb([
        [("⬅️ Назад до замовлення", f"tgord:open:{order_id}:0")],
    ])