from __future__ import annotations

import time
from typing import Any

from rent_platform.db.session import db_fetch_one, db_fetch_all, db_execute
from rent_platform.modules.telegram_shop.repo.products import ProductsRepo


class CategoriesRepo:
    @staticmethod
    async def has_any(tenant_id: str) -> bool:
        q = """
        SELECT 1 AS x
        FROM telegram_shop_categories
        WHERE tenant_id = :tid
        LIMIT 1
        """
        row = await db_fetch_one(q, {"tid": tenant_id})
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
        return await db_fetch_all(q, {"tid": tenant_id, "lim": int(limit)}) or []

    @staticmethod
    async def create(tenant_id: str, name: str, *, sort: int = 0) -> int | None:
        q = """
        INSERT INTO telegram_shop_categories (tenant_id, name, sort, created_ts)
        VALUES (:tid, :n, :s, :ts)
        RETURNING id
        """
        row = await db_fetch_one(
            q,
            {
                "tid": str(tenant_id),
                "n": (name or "").strip()[:64],
                "s": int(sort),
                "ts": int(time.time()),
            },
        )
        return int(row["id"]) if row and row.get("id") is not None else None

    @staticmethod
    async def get_default_id(tenant_id: str) -> int | None:
        q = """
        SELECT id
        FROM telegram_shop_categories
        WHERE tenant_id = :tid
        ORDER BY sort ASC, id ASC
        LIMIT 1
        """
        row = await db_fetch_one(q, {"tid": tenant_id})
        return int(row["id"]) if row and row.get("id") is not None else None

    @staticmethod
    async def ensure_default(tenant_id: str) -> int | None:
        """
        Гарантує, що у tenant є хоча б 1 категорія.
        Якщо нема — створює "Без категорії" і проставляє її всім товарам,
        у яких category_id IS NULL.
        """
        cid = await CategoriesRepo.get_default_id(tenant_id)
        if cid:
            # на всякий: підчистимо NULL у товарах
            await ProductsRepo.backfill_category_for_all_products(tenant_id, cid)
            return cid

        cid = await CategoriesRepo.create(tenant_id, "Без категорії", sort=0)
        if cid:
            await ProductsRepo.backfill_category_for_all_products(tenant_id, cid)
        return cid