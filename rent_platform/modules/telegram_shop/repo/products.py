from __future__ import annotations

import time
from typing import Any

from rent_platform.db.session import db_fetch_one, db_fetch_all, db_execute


class ProductsRepo:
    """
    Repo для товарів Telegram Shop.
    Працює через PostgreSQL.

    Таблиця очікується:
      telegram_shop_products(
        id serial pk,
        tenant_id text not null,
        name text not null,
        price_kop int not null default 0,
        is_active bool not null default true,
        created_ts int not null default 0
      )
    """

    @staticmethod
    async def list(tenant_id: str, limit: int = 50) -> list[dict[str, Any]]:
        q = """
        SELECT id, name, price_kop
        FROM telegram_shop_products
        WHERE tenant_id = :tid AND is_active = true
        ORDER BY id DESC
        LIMIT :lim
        """
        rows = await db_fetch_all(q, {"tid": str(tenant_id), "lim": int(limit)})
        return rows or []

    @staticmethod
    async def get(tenant_id: str, product_id: int) -> dict[str, Any] | None:
        q = """
        SELECT id, name, price_kop
        FROM telegram_shop_products
        WHERE tenant_id = :tid AND id = :pid AND is_active = true
        """
        return await db_fetch_one(q, {"tid": str(tenant_id), "pid": int(product_id)})

    @staticmethod
    async def add(tenant_id: str, name: str, price_kop: int) -> int | None:
        q = """
        INSERT INTO telegram_shop_products (tenant_id, name, price_kop, is_active, created_ts)
        VALUES (:tid, :n, :p, true, :ts)
        RETURNING id
        """
        row = await db_fetch_one(q, {
            "tid": str(tenant_id),
            "n": (name or "").strip()[:128],
            "p": int(price_kop),
            "ts": int(time.time()),
        })
        if not row or row.get("id") is None:
            return None
        return int(row["id"])

    @staticmethod
    async def deactivate(tenant_id: str, product_id: int) -> None:
        q = """
        UPDATE telegram_shop_products
        SET is_active = false
        WHERE tenant_id = :tid AND id = :pid
        """
        await db_execute(q, {"tid": str(tenant_id), "pid": int(product_id)})