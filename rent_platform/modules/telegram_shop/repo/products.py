from __future__ import annotations

import time
from typing import Any

from rent_platform.db.session import db_fetch_one, db_fetch_all, db_execute


class ProductsRepo:
    @staticmethod
    async def list_active(tenant_id: str, limit: int = 50) -> list[dict[str, Any]]:
        q = """
        SELECT id, tenant_id, name, price_kop, description, is_active, created_ts
        FROM telegram_shop_products
        WHERE tenant_id = :tid AND is_active = true
        ORDER BY id DESC
        LIMIT :lim
        """
        return await db_fetch_all(q, {"tid": tenant_id, "lim": int(limit)}) or []

    @staticmethod
    async def get_active(tenant_id: str, product_id: int) -> dict | None:
        q = """
        SELECT id, tenant_id, name, price_kop, description, is_active, created_ts
        FROM telegram_shop_products
        WHERE tenant_id = :tid AND id = :pid AND is_active = true
        """
        return await db_fetch_one(q, {"tid": tenant_id, "pid": int(product_id)})

    @staticmethod
    async def get_first_active(tenant_id: str) -> dict | None:
        q = """
        SELECT id, tenant_id, name, price_kop, description, is_active, created_ts
        FROM telegram_shop_products
        WHERE tenant_id = :tid AND is_active = true
        ORDER BY id ASC
        LIMIT 1
        """
        return await db_fetch_one(q, {"tid": tenant_id})

    @staticmethod
    async def get_next_active(tenant_id: str, current_id: int) -> dict | None:
        q = """
        SELECT id, tenant_id, name, price_kop, description, is_active, created_ts
        FROM telegram_shop_products
        WHERE tenant_id = :tid AND is_active = true AND id > :cid
        ORDER BY id ASC
        LIMIT 1
        """
        return await db_fetch_one(q, {"tid": tenant_id, "cid": int(current_id)})

    @staticmethod
    async def get_prev_active(tenant_id: str, current_id: int) -> dict | None:
        q = """
        SELECT id, tenant_id, name, price_kop, description, is_active, created_ts
        FROM telegram_shop_products
        WHERE tenant_id = :tid AND is_active = true AND id < :cid
        ORDER BY id DESC
        LIMIT 1
        """
        return await db_fetch_one(q, {"tid": tenant_id, "cid": int(current_id)})

    # --- description hooks (admin will use later) ---
    @staticmethod
    async def set_description(tenant_id: str, product_id: int, description: str) -> None:
        q = """
        UPDATE telegram_shop_products
        SET description = :d
        WHERE tenant_id = :tid AND id = :pid
        """
        await db_execute(q, {"tid": tenant_id, "pid": int(product_id), "d": (description or "").strip()[:4000]})

    # --- photos hooks (admin will use later) ---
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

    @staticmethod
    async def add_photo(tenant_id: str, product_id: int, file_id: str, *, sort: int = 0) -> int | None:
        q = """
        INSERT INTO telegram_shop_product_photos (tenant_id, product_id, file_id, sort, created_ts)
        VALUES (:tid, :pid, :fid, :s, :ts)
        RETURNING id
        """
        row = await db_fetch_one(q, {
            "tid": tenant_id,
            "pid": int(product_id),
            "fid": (file_id or "").strip(),
            "s": int(sort),
            "ts": int(time.time()),
        })
        return int(row["id"]) if row and row.get("id") is not None else None

    @staticmethod
    async def delete_photo(tenant_id: str, photo_id: int) -> None:
        q = "DELETE FROM telegram_shop_product_photos WHERE tenant_id = :tid AND id = :id"
        await db_execute(q, {"tid": tenant_id, "id": int(photo_id)})