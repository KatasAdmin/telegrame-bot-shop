# -*- coding: utf-8 -*-
from __future__ import annotations

STATUS_LABELS: dict[str, str] = {
    "new": "🆕 Створено",
    "confirmed": "✅ Прийнято",
    "packed": "📦 Зібрано",
    "shipped": "🚚 Відправлено",
    "in_transit": "🛣 В дорозі",
    "ready_pickup": "🏬 Чекає у відділенні",

    "delivered": "🎉 Отримано",
    "completed": "✅ Завершено",

    "canceled": "❌ Скасовано",
    "not_received": "⚠️ Не отримано",
    "returned": "↩️ Повернення",
    "failed": "⛔ Помилка",
    "expired": "⌛ Прострочено",
}

FINAL_STATUSES: set[str] = {
    "delivered", "completed",
    "canceled", "not_received", "returned", "failed", "expired",
}

def status_label(status: str) -> str:
    s = (status or "").strip()
    return STATUS_LABELS.get(s, f"ℹ️ {s or 'невідомо'}")