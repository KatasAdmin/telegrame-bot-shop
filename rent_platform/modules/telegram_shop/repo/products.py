from __future__ import annotations

import time
from typing import Any

from rent_platform.db.session import db_fetch_all, db_fetch_one, db_execute


class TelegramShopProductsRepo:
    @staticmethod
    async def list_products(tenant_id: str, limit: int = 50) -> list[dict[str, Any]]:
        q = """
        SELECT
            id,
            name,
            price_kop,
            is_active,
            COALESCE(is_hit, false) AS is_hit,
            COALESCE(promo_price_kop, 0) AS promo_price_kop,
            COALESCE(promo_until_ts, 0) AS promo_until_ts
        FROM telegram_shop_products
        WHERE tenant_id = :tid AND is_active = true
        ORDER BY id DESC
        LIMIT :lim
        """
        rows = await db_fetch_all(q, {"tid": tenant_id, "lim": int(limit)}) or []
        return rows

    @staticmethod
    async def get_product(tenant_id: str, product_id: int) -> dict | None:
        q = """
        SELECT
            id,
            name,
            price_kop,
            is_active,
            COALESCE(is_hit, false) AS is_hit,
            COALESCE(promo_price_kop, 0) AS promo_price_kop,
            COALESCE(promo_until_ts, 0) AS promo_until_ts
        FROM telegram_shop_products
        WHERE tenant_id = :tid AND id = :pid AND is_active = true
        """
        return await db_fetch_one(q, {"tid": tenant_id, "pid": int(product_id)})

    @staticmethod
    async def add_product(tenant_id: str, name: str, price_kop: int) -> int | None:
        q = """
        INSERT INTO telegram_shop_products (
            tenant_id, name, price_kop, is_active, created_ts,
            is_hit, promo_price_kop, promo_until_ts
        )
        VALUES (:tid, :n, :p, true, :ts, false, 0, 0)
        RETURNING id
        """
        row = await db_fetch_one(
            q,
            {
                "tid": tenant_id,
                "n": (name or "").strip()[:128],
                "p": int(price_kop),
                "ts": int(time.time()),
            },
        )
        return int(row["id"]) if row and row.get("id") is not None else None

    @staticmethod
    async def set_hit(tenant_id: str, product_id: int, is_hit: bool) -> None:
        q = """
        UPDATE telegram_shop_products
        SET is_hit = :h
        WHERE tenant_id = :tid AND id = :pid
        """
        await db_execute(q, {"tid": tenant_id, "pid": int(product_id), "h": bool(is_hit)})

    @staticmethod
    async def set_promo(tenant_id: str, product_id: int, promo_price_kop: int, promo_until_ts: int) -> None:
        q = """
        UPDATE telegram_shop_products
        SET promo_price_kop = :pp, promo_until_ts = :pu
        WHERE tenant_id = :tid AND id = :pid
        """
        await db_execute(
            q,
            {
                "tid": tenant_id,
                "pid": int(product_id),
                "pp": int(promo_price_kop),
                "pu": int(promo_until_ts),
            },
        )