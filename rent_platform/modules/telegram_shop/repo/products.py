from __future__ import annotations

import time
from typing import Any

from rent_platform.db.session import db_fetch_one, db_fetch_all, db_execute


class ProductsRepo:
    # --------- products list/get (active) ---------

    @staticmethod
    async def list_active(tenant_id: str, limit: int = 50) -> list[dict[str, Any]]:
        q = """
        SELECT
            id,
            tenant_id,
            category_id,
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
        ORDER BY id ASC
        LIMIT :lim
        """
        return await db_fetch_all(q, {"tid": tenant_id, "lim": int(limit)}) or []

    @staticmethod
    async def list_inactive(tenant_id: str, limit: int = 50) -> list[dict[str, Any]]:
        q = """
        SELECT
            id,
            tenant_id,
            category_id,
            name,
            price_kop,
            is_active,
            COALESCE(is_hit, false) AS is_hit,
            COALESCE(promo_price_kop, 0) AS promo_price_kop,
            COALESCE(promo_until_ts, 0) AS promo_until_ts,
            COALESCE(description, '') AS description,
            created_ts
        FROM telegram_shop_products
        WHERE tenant_id = :tid AND is_active = false
        ORDER BY id ASC
        LIMIT :lim
        """
        return await db_fetch_all(q, {"tid": tenant_id, "lim": int(limit)}) or []

    @staticmethod
    async def get_active(tenant_id: str, product_id: int) -> dict | None:
        q = """
        SELECT
            id,
            tenant_id,
            category_id,
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
    async def add(
        tenant_id: str,
        name: str,
        price_kop: int,
        *,
        is_hit: bool = False,
        promo_price_kop: int = 0,
        promo_until_ts: int = 0,
        is_active: bool = True,
        category_id: int | None = None,
    ) -> int | None:
        q = """
        INSERT INTO telegram_shop_products
            (tenant_id, name, price_kop, is_active, is_hit, promo_price_kop, promo_until_ts, category_id, created_ts)
        VALUES
            (:tid, :n, :p, :a, :h, :pp, :pu, :cid, :ts)
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
                "cid": int(category_id) if category_id is not None else None,
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
    async def set_category(tenant_id: str, product_id: int, category_id: int | None) -> None:
        q = """
        UPDATE telegram_shop_products
        SET category_id = :cid
        WHERE tenant_id = :tid AND id = :pid
        """
        await db_execute(
            q,
            {"tid": tenant_id, "pid": int(product_id), "cid": int(category_id) if category_id is not None else None},
        )

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

    # --------- navigation helpers (for catalog cards) ---------

    @staticmethod
    async def get_first_active(tenant_id: str, category_id: int | None = None) -> dict | None:
        if category_id is None:
            q = """
            SELECT id
            FROM telegram_shop_products
            WHERE tenant_id = :tid AND is_active = true
            ORDER BY id ASC
            LIMIT 1
            """
            return await db_fetch_one(q, {"tid": tenant_id})

        q = """
        SELECT id
        FROM telegram_shop_products
        WHERE tenant_id = :tid AND is_active = true AND category_id = :cid
        ORDER BY id ASC
        LIMIT 1
        """
        return await db_fetch_one(q, {"tid": tenant_id, "cid": int(category_id)})

    @staticmethod
    async def get_prev_active(tenant_id: str, product_id: int, category_id: int | None = None) -> dict | None:
        if category_id is None:
            q = """
            SELECT id
            FROM telegram_shop_products
            WHERE tenant_id = :tid AND is_active = true AND id < :pid
            ORDER BY id DESC
            LIMIT 1
            """
            return await db_fetch_one(q, {"tid": tenant_id, "pid": int(product_id)})

        q = """
        SELECT id
        FROM telegram_shop_products
        WHERE tenant_id = :tid AND is_active = true AND category_id = :cid AND id < :pid
        ORDER BY id DESC
        LIMIT 1
        """
        return await db_fetch_one(q, {"tid": tenant_id, "cid": int(category_id), "pid": int(product_id)})

    @staticmethod
    async def get_next_active(tenant_id: str, product_id: int, category_id: int | None = None) -> dict | None:
        if category_id is None:
            q = """
            SELECT id
            FROM telegram_shop_products
            WHERE tenant_id = :tid AND is_active = true AND id > :pid
            ORDER BY id ASC
            LIMIT 1
            """
            return await db_fetch_one(q, {"tid": tenant_id, "pid": int(product_id)})

        q = """
        SELECT id
        FROM telegram_shop_products
        WHERE tenant_id = :tid AND is_active = true AND category_id = :cid AND id > :pid
        ORDER BY id ASC
        LIMIT 1
        """
        return await db_fetch_one(q, {"tid": tenant_id, "cid": int(category_id), "pid": int(product_id)})

    # --------- description ---------

    @staticmethod
    async def set_description(tenant_id: str, product_id: int, description: str) -> None:
        q = """
        UPDATE telegram_shop_products
        SET description = :d
        WHERE tenant_id = :tid AND id = :pid
        """
        await db_execute(q, {"tid": tenant_id, "pid": int(product_id), "d": (description or "").strip()})

    # --------- product photos (Telegram file_id) ---------

    @staticmethod
    async def add_product_photo(tenant_id: str, product_id: int, file_id: str) -> int | None:
        q_sort = """
        SELECT COALESCE(MAX(sort), 0) AS mx
        FROM telegram_shop_product_photos
        WHERE tenant_id = :tid AND product_id = :pid
        """
        row = await db_fetch_one(q_sort, {"tid": tenant_id, "pid": int(product_id)})
        next_sort = int(row["mx"] or 0) + 1 if row else 1

        q = """
        INSERT INTO telegram_shop_product_photos (tenant_id, product_id, file_id, sort, created_ts)
        VALUES (:tid, :pid, :fid, :s, :ts)
        RETURNING id
        """
        ins = await db_fetch_one(
            q,
            {"tid": tenant_id, "pid": int(product_id), "fid": str(file_id), "s": int(next_sort), "ts": int(time.time())},
        )
        return int(ins["id"]) if ins and ins.get("id") is not None else None

    @staticmethod
    async def list_product_photos(tenant_id: str, product_id: int, limit: int = 10) -> list[dict[str, Any]]:
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


    @staticmethod
    async def list_active(tenant_id: str, limit: int = 50, *, category_id: int | None = None) -> list[dict[str, Any]]:
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
            category_id,
            created_ts
        FROM telegram_shop_products
        WHERE tenant_id = :tid AND is_active = true
          AND (:cid IS NULL OR category_id = :cid)
        ORDER BY id ASC
        LIMIT :lim
        """
        return await db_fetch_all(q, {"tid": tenant_id, "lim": int(limit), "cid": category_id}) or []

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
            category_id,
            created_ts
        FROM telegram_shop_products
        WHERE tenant_id = :tid AND id = :pid AND is_active = true
        """
        return await db_fetch_one(q, {"tid": tenant_id, "pid": int(product_id)})

    @staticmethod
    async def get_first_active(tenant_id: str, *, category_id: int | None = None) -> dict | None:
        q = """
        SELECT id
        FROM telegram_shop_products
        WHERE tenant_id = :tid AND is_active = true
          AND (:cid IS NULL OR category_id = :cid)
        ORDER BY id ASC
        LIMIT 1
        """
        return await db_fetch_one(q, {"tid": tenant_id, "cid": category_id})

    @staticmethod
    async def get_prev_active(tenant_id: str, product_id: int, *, category_id: int | None = None) -> dict | None:
        q = """
        SELECT id
        FROM telegram_shop_products
        WHERE tenant_id = :tid AND is_active = true AND id < :pid
          AND (:cid IS NULL OR category_id = :cid)
        ORDER BY id DESC
        LIMIT 1
        """
        return await db_fetch_one(q, {"tid": tenant_id, "pid": int(product_id), "cid": category_id})

    @staticmethod
    async def get_next_active(tenant_id: str, product_id: int, *, category_id: int | None = None) -> dict | None:
        q = """
        SELECT id
        FROM telegram_shop_products
        WHERE tenant_id = :tid AND is_active = true AND id > :pid
          AND (:cid IS NULL OR category_id = :cid)
        ORDER BY id ASC
        LIMIT 1
        """
        return await db_fetch_one(q, {"tid": tenant_id, "pid": int(product_id), "cid": category_id})