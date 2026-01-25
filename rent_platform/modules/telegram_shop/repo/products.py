from __future__ import annotations

import time
from typing import Any

from rent_platform.db.session import db_fetch_one, db_fetch_all, db_execute


class ProductsRepo:
    """
    MODE B (no hits/promos columns yet).
    Works with columns: id, tenant_id, name, price_kop, is_active, created_ts
    """

    @staticmethod
    async def list_active(tenant_id: str, limit: int = 50) -> list[dict[str, Any]]:
        q = """
        SELECT
            id,
            tenant_id,
            name,
            price_kop,
            is_active,
            created_ts
        FROM telegram_shop_products
        WHERE tenant_id = :tid AND is_active = true
        ORDER BY id DESC
        LIMIT :lim
        """
        return await db_fetch_all(q, {"tid": tenant_id, "lim": int(limit)}) or []

    @staticmethod
    async def get_active(tenant_id: str, product_id: int) -> dict | None:
        q = """
        SELECT
            id,
            tenant_id,
            name,
            price_kop,
            is_active,
            created_ts
        FROM telegram_shop_products
        WHERE tenant_id = :tid AND id = :pid AND is_active = true
        """
        return await db_fetch_one(q, {"tid": tenant_id, "pid": int(product_id)})

    @staticmethod
    async def add(
        tenant_id: str,
        name: str,
        price_kop: int,
        *,
        is_active: bool = True,
    ) -> int | None:
        """
        MODE B insert (no hits/promos columns).
        """
        q = """
        INSERT INTO telegram_shop_products
            (tenant_id, name, price_kop, is_active, created_ts)
        VALUES
            (:tid, :n, :p, :a, :ts)
        RETURNING id
        """
        row = await db_fetch_one(
            q,
            {
                "tid": str(tenant_id),
                "n": (name or "").strip()[:128],
                "p": int(price_kop),
                "a": bool(is_active),
                "ts": int(time.time()),
            },
        )
        return int(row["id"]) if row and row.get("id") is not None else None

    @staticmethod
    async def set_active(tenant_id: str, product_id: int, is_active: bool) -> None:
        q = """
        UPDATE telegram_shop_products
        SET is_active = :a
        WHERE tenant_id = :tid AND id = :pid
        """
        await db_execute(q, {"tid": tenant_id, "pid": int(product_id), "a": bool(is_active)})