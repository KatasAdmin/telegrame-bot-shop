from __future__ import annotations

import time
from typing import Any

from rent_platform.db.session import db_fetch_one, db_fetch_all, db_execute


class CategoriesRepo:
    DEFAULT_NAME = "Без категорії"

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
    async def create(tenant_id: str, name: str, sort: int = 100) -> int | None:
        q = """
        INSERT INTO telegram_shop_categories (tenant_id, name, sort, created_ts)
        VALUES (:tid, :name, :sort, :ts)
        RETURNING id
        """
        row = await db_fetch_one(
            q,
            {"tid": str(tenant_id), "name": (name or "").strip()[:64], "sort": int(sort), "ts": int(time.time())},
        )
        return int(row["id"]) if row and row.get("id") is not None else None

    @staticmethod
    async def get_default_id(tenant_id: str) -> int | None:
        q = """
        SELECT id
        FROM telegram_shop_categories
        WHERE tenant_id = :tid AND name = :name
        ORDER BY sort ASC, id ASC
        LIMIT 1
        """
        row = await db_fetch_one(q, {"tid": str(tenant_id), "name": CategoriesRepo.DEFAULT_NAME})
        return int(row["id"]) if row and row.get("id") is not None else None

    @staticmethod
    async def ensure_default(tenant_id: str) -> int:
        """
        Гарантує існування дефолтної категорії "Без категорії".
        Повертає її id.
        """
        cid = await CategoriesRepo.get_default_id(tenant_id)
        if cid:
            return int(cid)
        new_id = await CategoriesRepo.create(tenant_id, CategoriesRepo.DEFAULT_NAME, sort=0)
        return int(new_id or 0)