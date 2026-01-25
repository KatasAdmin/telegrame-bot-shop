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
        SELECT id, tenant_id, name, created_ts
        FROM telegram_shop_categories
        WHERE tenant_id = :tid
        ORDER BY id ASC
        LIMIT :lim
        """
        return await db_fetch_all(q, {"tid": str(tenant_id), "lim": int(limit)}) or []

    @staticmethod
    async def get_first(tenant_id: str) -> dict | None:
        q = """
        SELECT id, name
        FROM telegram_shop_categories
        WHERE tenant_id = :tid
        ORDER BY id ASC
        LIMIT 1
        """
        return await db_fetch_one(q, {"tid": str(tenant_id)})

    @staticmethod
    async def create(tenant_id: str, name: str) -> int | None:
        """
        Правило:
        - Категорії необовʼязкові, поки їх немає.
        - Як тільки створена 1 категорія: всі старі товари, що були без категорії -> автоматом у першу категорію.
        """
        tenant_id = str(tenant_id)
        name = (name or "").strip()[:64]
        if not name:
            return None

        # чи це перша категорія?
        had_any = await CategoriesRepo.has_any(tenant_id)

        q = """
        INSERT INTO telegram_shop_categories (tenant_id, name, created_ts)
        VALUES (:tid, :n, :ts)
        RETURNING id
        """
        row = await db_fetch_one(q, {"tid": tenant_id, "n": name, "ts": int(time.time())})
        if not row or row.get("id") is None:
            return None

        cid = int(row["id"])

        # якщо це перша категорія — “приклеїти” до не категоризованих товарів
        if not had_any:
            q_upd = """
            UPDATE telegram_shop_products
            SET category_id = :cid
            WHERE tenant_id = :tid AND category_id IS NULL
            """
            await db_execute(q_upd, {"tid": tenant_id, "cid": cid})

        return cid