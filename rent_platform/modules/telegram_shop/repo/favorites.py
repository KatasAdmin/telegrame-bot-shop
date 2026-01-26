from __future__ import annotations

import time
from typing import Any

from rent_platform.db.session import db_fetch_all, db_fetch_one, db_execute


class TelegramShopFavoritesRepo:
    """
    Table expected:
      telegram_shop_favorites (
        tenant_id text,
        user_id bigint,
        product_id int,
        created_ts int,
        PRIMARY KEY (tenant_id, user_id, product_id)
      )
    """

    @staticmethod
    async def add(tenant_id: str, user_id: int, product_id: int) -> None:
        q = """
        INSERT INTO telegram_shop_favorites (tenant_id, user_id, product_id, created_ts)
        VALUES (:tid, :uid, :pid, :ts)
        ON CONFLICT (tenant_id, user_id, product_id) DO NOTHING
        """
        await db_execute(
            q,
            {"tid": str(tenant_id), "uid": int(user_id), "pid": int(product_id), "ts": int(time.time())},
        )

    @staticmethod
    async def remove(tenant_id: str, user_id: int, product_id: int) -> None:
        q = """
        DELETE FROM telegram_shop_favorites
        WHERE tenant_id = :tid AND user_id = :uid AND product_id = :pid
        """
        await db_execute(q, {"tid": str(tenant_id), "uid": int(user_id), "pid": int(product_id)})

    @staticmethod
    async def is_fav(tenant_id: str, user_id: int, product_id: int) -> bool:
        q = """
        SELECT 1
        FROM telegram_shop_favorites
        WHERE tenant_id = :tid AND user_id = :uid AND product_id = :pid
        LIMIT 1
        """
        row = await db_fetch_one(q, {"tid": str(tenant_id), "uid": int(user_id), "pid": int(product_id)})
        return bool(row)

    @staticmethod
    async def toggle(tenant_id: str, user_id: int, product_id: int) -> bool:
        """
        Returns True if added, False if removed.
        """
        if await TelegramShopFavoritesRepo.is_fav(tenant_id, user_id, product_id):
            await TelegramShopFavoritesRepo.remove(tenant_id, user_id, product_id)
            return False
        await TelegramShopFavoritesRepo.add(tenant_id, user_id, product_id)
        return True

    @staticmethod
    async def list_ids(tenant_id: str, user_id: int, limit: int = 200) -> list[int]:
        q = """
        SELECT f.product_id
        FROM telegram_shop_favorites f
        JOIN telegram_shop_products p
          ON p.tenant_id = f.tenant_id AND p.id = f.product_id
        WHERE f.tenant_id = :tid AND f.user_id = :uid AND p.is_active = true
        ORDER BY f.created_ts DESC, f.product_id DESC
        LIMIT :lim
        """
        rows = await db_fetch_all(q, {"tid": str(tenant_id), "uid": int(user_id), "lim": int(limit)}) or []
        return [int(r["product_id"]) for r in rows if r and r.get("product_id") is not None]

    @staticmethod
    async def get_first(tenant_id: str, user_id: int) -> int | None:
        q = """
        SELECT f.product_id
        FROM telegram_shop_favorites f
        JOIN telegram_shop_products p
          ON p.tenant_id = f.tenant_id AND p.id = f.product_id
        WHERE f.tenant_id = :tid AND f.user_id = :uid AND p.is_active = true
        ORDER BY f.created_ts DESC, f.product_id DESC
        LIMIT 1
        """
        row = await db_fetch_one(q, {"tid": str(tenant_id), "uid": int(user_id)})
        return int(row["product_id"]) if row and row.get("product_id") is not None else None

    @staticmethod
    async def get_prev(tenant_id: str, user_id: int, product_id: int) -> int | None:
        ids = await TelegramShopFavoritesRepo.list_ids(tenant_id, user_id, limit=500)
        if not ids:
            return None
        try:
            i = ids.index(int(product_id))
        except ValueError:
            return ids[0]
        return ids[i - 1] if i - 1 >= 0 else None

    @staticmethod
    async def get_next(tenant_id: str, user_id: int, product_id: int) -> int | None:
        ids = await TelegramShopFavoritesRepo.list_ids(tenant_id, user_id, limit=500)
        if not ids:
            return None
        try:
            i = ids.index(int(product_id))
        except ValueError:
            return ids[0]
        return ids[i + 1] if i + 1 < len(ids) else None