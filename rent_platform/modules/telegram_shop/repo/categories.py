from __future__ import annotations

import time
from typing import Any

from rent_platform.db.session import db_fetch_one, db_fetch_all, db_execute


class CategoriesRepo:
    DEFAULT_NAME = "Без категорії"
    DEFAULT_HIDDEN_SORT = -100

    @staticmethod
    async def ensure_default(tenant_id: str) -> int:
        """
        Гарантує категорію DEFAULT_NAME для tenant і повертає її id.
        """
        name = CategoriesRepo.DEFAULT_NAME

        q_ins = """
        INSERT INTO telegram_shop_categories (tenant_id, name, sort, created_ts)
        VALUES (:tid, :name, 0, :ts)
        ON CONFLICT (tenant_id, name) DO NOTHING
        RETURNING id
        """
        row = await db_fetch_one(q_ins, {"tid": tenant_id, "name": name, "ts": int(time.time())})
        if row and row.get("id") is not None:
            return int(row["id"])

        q_get = """
        SELECT id
        FROM telegram_shop_categories
        WHERE tenant_id = :tid AND name = :name
        LIMIT 1
        """
        row2 = await db_fetch_one(q_get, {"tid": tenant_id, "name": name})
        return int(row2["id"])

    @staticmethod
    async def get_default(tenant_id: str) -> dict[str, Any] | None:
        q = """
        SELECT id, tenant_id, name, sort, created_ts
        FROM telegram_shop_categories
        WHERE tenant_id = :tid AND name = :name
        LIMIT 1
        """
        return await db_fetch_one(q, {"tid": tenant_id, "name": CategoriesRepo.DEFAULT_NAME})

    @staticmethod
    async def set_default_visible(tenant_id: str, visible: bool) -> None:
        """
        visible=True  -> sort = 0 (показувати)
        visible=False -> sort = -100 (ховати)
        """
        await CategoriesRepo.ensure_default(tenant_id)
        new_sort = 0 if visible else CategoriesRepo.DEFAULT_HIDDEN_SORT
        q = """
        UPDATE telegram_shop_categories
        SET sort = :s
        WHERE tenant_id = :tid AND name = :name
        """
        await db_execute(q, {"tid": tenant_id, "name": CategoriesRepo.DEFAULT_NAME, "s": int(new_sort)})

    @staticmethod
    async def is_default_visible(tenant_id: str) -> bool:
        row = await CategoriesRepo.get_default(tenant_id)
        if not row:
            return False
        return int(row.get("sort") or 0) >= 0

    @staticmethod
    async def list_public(tenant_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """
        Для покупця: тільки видимі категорії (sort >= 0)
        """
        q = """
        SELECT id, tenant_id, name, sort, created_ts
        FROM telegram_shop_categories
        WHERE tenant_id = :tid AND sort >= 0
        ORDER BY sort ASC, id ASC
        LIMIT :lim
        """
        return await db_fetch_all(q, {"tid": tenant_id, "lim": int(limit)}) or []

    @staticmethod
    async def list(tenant_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """
        Для адміна: всі категорії (включно приховані)
        """
        q = """
        SELECT id, tenant_id, name, sort, created_ts
        FROM telegram_shop_categories
        WHERE tenant_id = :tid
        ORDER BY sort ASC, id ASC
        LIMIT :lim
        """
        return await db_fetch_all(q, {"tid": tenant_id, "lim": int(limit)}) or []

    @staticmethod
    async def create(tenant_id: str, name: str, sort: int = 100) -> int:
        nm = (name or "").strip()[:64]
        if not nm:
            raise ValueError("empty category name")

        q_ins = """
        INSERT INTO telegram_shop_categories (tenant_id, name, sort, created_ts)
        VALUES (:tid, :name, :sort, :ts)
        ON CONFLICT (tenant_id, name) DO NOTHING
        RETURNING id
        """
        row = await db_fetch_one(q_ins, {"tid": tenant_id, "name": nm, "sort": int(sort), "ts": int(time.time())})
        if row and row.get("id") is not None:
            return int(row["id"])

        q_get = """
        SELECT id
        FROM telegram_shop_categories
        WHERE tenant_id = :tid AND name = :name
        LIMIT 1
        """
        row2 = await db_fetch_one(q_get, {"tid": tenant_id, "name": nm})
        return int(row2["id"])