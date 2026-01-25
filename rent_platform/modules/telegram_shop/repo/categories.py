from __future__ import annotations

import time
from typing import Any

from rent_platform.db.session import db_fetch_one, db_fetch_all, db_execute


class CategoriesRepo:
    @staticmethod
    async def list(tenant_id: str, limit: int = 100) -> list[dict[str, Any]]:
        q = """
        SELECT id, tenant_id, name, sort, created_ts
        FROM telegram_shop_categories
        WHERE tenant_id = :tid
        ORDER BY sort ASC, id ASC
        LIMIT :lim
        """
        return await db_fetch_all(q, {"tid": tenant_id, "lim": int(limit)}) or []

    @staticmethod
    async def count(tenant_id: str) -> int:
        q = "SELECT COUNT(*) AS c FROM telegram_shop_categories WHERE tenant_id = :tid"
        row = await db_fetch_one(q, {"tid": tenant_id})
        return int(row["c"] or 0) if row else 0

    @staticmethod
    async def add(tenant_id: str, name: str, sort: int = 0) -> int | None:
        q = """
        INSERT INTO telegram_shop_categories (tenant_id, name, sort, created_ts)
        VALUES (:tid, :n, :s, :ts)
        RETURNING id
        """
        row = await db_fetch_one(q, {"tid": tenant_id, "n": (name or "").strip()[:128], "s": int(sort), "ts": int(time.time())})
        return int(row["id"]) if row and row.get("id") is not None else None