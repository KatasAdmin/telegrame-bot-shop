from __future__ import annotations

import time
from typing import Any

from rent_platform.db.session import db_fetch_one, db_fetch_all, db_execute


class ProductsRepo:
    # -------- products --------

    @staticmethod
    async def list_active(tenant_id: str, limit: int = 50) -> list[dict[str, Any]]:
        q = """
        SELECT
            id,
            tenant_id,
            name,
            price_kop,
            is_active,
            COALESCE(is_hit, false) AS is_hit,
            COALESCE(promo_price_kop, 0) AS promo_price_kop,
            COALESCE(promo_until_ts, 0) AS promo_until_ts,
            COALESCE(description, '') AS description,
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
            COALESCE(is_hit, false) AS is_hit,
            COALESCE(promo_price_kop, 0) AS promo_price_kop,
            COALESCE(promo_until_ts, 0) AS promo_until_ts,
            COALESCE(description, '') AS description,
            created_ts
        FROM telegram_shop_products
        WHERE tenant_id = :tid AND id = :pid AND is_active = true
        """
        return await db_fetch_one(q, {"tid": tenant_id, "pid": int(product_id)})

    @staticmethod
    async def get_first_active(tenant_id: str) -> dict | None:
        q = """
        SELECT id
        FROM telegram_shop_products
        WHERE tenant_id = :tid AND is_active = true
        ORDER BY id ASC
        LIMIT 1
        """
        return await db_fetch_one(q, {"tid": tenant_id})

    @staticmethod
    async def get_prev_active(tenant_id: str, product_id: int) -> dict | None:
        q = """
        SELECT id
        FROM telegram_shop_products
        WHERE tenant_id = :tid AND is_active = true AND id < :pid
        ORDER BY id DESC
        LIMIT 1
        """
        return await db_fetch_one(q, {"tid": tenant_id, "pid": int(product_id)})

    @staticmethod
    async def get_next_active(tenant_id: str, product_id: int) -> dict | None:
        q = """
        SELECT id
        FROM telegram_shop_products
        WHERE tenant_id = :tid AND is_active = true AND id > :pid
        ORDER BY id ASC
        LIMIT 1
        """
        return await db_fetch_one(q, {"tid": tenant_id, "pid": int(product_id)})

    @staticmethod
    async def add(
        tenant_id: str,
        name: str,
        price_kop: int,
        *,
        is_hit: bool = False,
        promo_price_kop: int = 0,
        promo_until_ts: int = 0,
        is_active: bool = True,
        description: str = "",
    ) -> int | None:
        q = """
        INSERT INTO telegram_shop_products
            (tenant_id, name, price_kop, is_active, is_hit, promo_price_kop, promo_until_ts, description, created_ts)
        VALUES
            (:tid, :n, :p, :a, :h, :pp, :pu, :d, :ts)
        RETURNING id
        """
        row = await db_fetch_one(
            q,
            {
                "tid": str(tenant_id),
                "n": (name or "").strip()[:128],
                "p": int(price_kop),
                "a": bool(is_active),
                "h": bool(is_hit),
                "pp": int(promo_price_kop),
                "pu": int(promo_until_ts),
                "d": (description or "").strip(),
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
        SET promo_price_kop = :pp,
            promo_until_ts = :pu
        WHERE tenant_id = :tid AND id = :pid
        """
        await db_execute(
            q,
            {"tid": tenant_id, "pid": int(product_id), "pp": int(promo_price_kop), "pu": int(promo_until_ts)},
        )

    @staticmethod
    async def set_description(tenant_id: str, product_id: int, description: str) -> None:
        q = """
        UPDATE telegram_shop_products
        SET description = :d
        WHERE tenant_id = :tid AND id = :pid
        """
        await db_execute(q, {"tid": tenant_id, "pid": int(product_id), "d": (description or "").strip()})


    # -------- photos --------

    @staticmethod
    async def add_photo(tenant_id: str, product_id: int, file_id: str, *, sort: int = 0) -> int | None:
        q = """
        INSERT INTO telegram_shop_product_photos (tenant_id, product_id, file_id, sort, created_ts)
        VALUES (:tid, :pid, :fid, :s, :ts)
        RETURNING id
        """
        row = await db_fetch_one(
            q,
            {"tid": tenant_id, "pid": int(product_id), "fid": str(file_id), "s": int(sort), "ts": int(time.time())},
        )
        return int(row["id"]) if row and row.get("id") is not None else None

    @staticmethod
    async def list_photos(tenant_id: str, product_id: int, limit: int = 10) -> list[dict[str, Any]]:
        q = """
        SELECT id, tenant_id, product_id, file_id, sort, created_ts
        FROM telegram_shop_product_photos
        WHERE tenant_id = :tid AND product_id = :pid
        ORDER BY sort ASC, id ASC
        LIMIT :lim
        """
        return await db_fetch_all(q, {"tid": tenant_id, "pid": int(product_id), "lim": int(limit)}) or []

    @staticmethod
    async def get_cover_photo_file_id(tenant_id: str, product_id: int) -> str | None:
        q = """
        SELECT file_id
        FROM telegram_shop_product_photos
        WHERE tenant_id = :tid AND product_id = :pid
        ORDER BY sort ASC, id ASC
        LIMIT 1
        """
        row = await db_fetch_one(q, {"tid": tenant_id, "pid": int(product_id)})
        return str(row["file_id"]) if row and row.get("file_id") else None