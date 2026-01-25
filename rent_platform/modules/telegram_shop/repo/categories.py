from __future__ import annotations

import time
from typing import Any

from rent_platform.db.session import db_fetch_one, db_fetch_all, db_execute


class CategoriesRepo:
    DEFAULT_NAME = "Без категорії"

    @staticmethod
    async def ensure_default(tenant_id: str) -> int:
        """
        Гарантує категорію "Без категорії" для tenant і повертає її id.
        Не падає, якщо вже існує.
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
    async def create(tenant_id: str, name: str, sort: int = 100) -> int:
        """
        Створює категорію. Якщо така назва вже є — не падає, повертає існуючу.
        """
        nm = (name or "").strip()[:64]
        if not nm:
            raise ValueError("empty category name")

        q_ins = """
        INSERT INTO telegram_shop_categories (tenant_id, name, sort, created_ts)
        VALUES (:tid, :name, :sort, :ts)
        ON CONFLICT (tenant_id, name) DO NOTHING
        RETURNING id
        """
        row = await db_fetch_one(
            q_ins,
            {"tid": tenant_id, "name": nm, "sort": int(sort), "ts": int(time.time())},
        )
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

    @staticmethod
    async def delete(tenant_id: str, category_id: int) -> None:
        """
        Видаляє категорію (крім "Без категорії").
        Перед видаленням переносить всі товари з цієї категорії в дефолтну.
        """
        cid = int(category_id)
        default_id = await CategoriesRepo.ensure_default(tenant_id)
        if cid == int(default_id):
            raise ValueError("cannot delete default category")

        # Переносимо товари в "Без категорії"
        q_move = """
        UPDATE telegram_shop_products
        SET category_id = :to_cid
        WHERE tenant_id = :tid AND category_id = :cid
        """
        await db_execute(q_move, {"tid": tenant_id, "cid": cid, "to_cid": int(default_id)})

        # Видаляємо категорію
        q_del = """
        DELETE FROM telegram_shop_categories
        WHERE tenant_id = :tid AND id = :cid
        """
        await db_execute(q_del, {"tid": tenant_id, "cid": cid})
