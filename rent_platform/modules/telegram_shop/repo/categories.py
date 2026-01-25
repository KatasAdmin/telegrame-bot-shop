from __future__ import annotations

import time
from typing import Any

from rent_platform.db.session import db_fetch_one, db_fetch_all, db_execute


class CategoriesRepo:
    @staticmethod
    async def has_any(tenant_id: str) -> bool:
        q = """
        SELECT 1
        FROM telegram_shop_categories
        WHERE tenant_id = :tid
        LIMIT 1
        """
        row = await db_fetch_one(q, {"tid": str(tenant_id)})
        return bool(row)

    @staticmethod
    async def list(tenant_id: str, limit: int = 50) -> list[dict[str, Any]]:
        q = """
        SELECT id, tenant_id, name, sort, created_ts
        FROM telegram_shop_categories
        WHERE tenant_id = :tid
        ORDER BY sort ASC, id ASC
        LIMIT :lim
        """
        return await db_fetch_all(q, {"tid": str(tenant_id), "lim": int(limit)}) or []

    @staticmethod
    async def create(tenant_id: str, name: str, sort: int = 0) -> int | None:
        q = """
        INSERT INTO telegram_shop_categories (tenant_id, name, sort, created_ts)
        VALUES (:tid, :n, :s, :ts)
        ON CONFLICT (tenant_id, name) DO UPDATE SET name = EXCLUDED.name
        RETURNING id
        """
        row = await db_fetch_one(
            q,
            {"tid": str(tenant_id), "n": (name or "").strip()[:64], "s": int(sort), "ts": int(time.time())},
        )
        return int(row["id"]) if row and row.get("id") is not None else None

    @staticmethod
    async def ensure_default_category_id(tenant_id: str) -> int | None:
        """
        Гарантує, що існує категорія 'Без категорії' і повертає її id.
        """
        q_sel = """
        SELECT id
        FROM telegram_shop_categories
        WHERE tenant_id = :tid AND name = 'Без категорії'
        LIMIT 1
        """
        row = await db_fetch_one(q_sel, {"tid": str(tenant_id)})
        if row and row.get("id") is not None:
            return int(row["id"])

        cid = await CategoriesRepo.create(tenant_id, "Без категорії", sort=0)
        return int(cid) if cid else None

    @staticmethod
    async def get_by_id(tenant_id: str, category_id: int) -> dict[str, Any] | None:
        q = """
        SELECT id, tenant_id, name, sort, created_ts
        FROM telegram_shop_categories
        WHERE tenant_id = :tid AND id = :cid
        """
        return await db_fetch_one(q, {"tid": str(tenant_id), "cid": int(category_id)})