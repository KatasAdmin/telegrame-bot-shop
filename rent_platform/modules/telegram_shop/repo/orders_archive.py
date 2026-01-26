# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from rent_platform.db.session import db_fetch_one, db_execute

class TelegramShopOrdersArchiveRepo:
    """
    Table expected:
      telegram_shop_orders_archive (
        tenant_id text,
        user_id bigint,
        order_id int,
        archived_ts int,
        PRIMARY KEY (tenant_id, user_id, order_id)
      )
    """

    @staticmethod
    async def is_archived(tenant_id: str, user_id: int, order_id: int) -> bool:
        q = """
        SELECT 1
        FROM telegram_shop_orders_archive
        WHERE tenant_id = :tid AND user_id = :uid AND order_id = :oid
        LIMIT 1
        """
        row = await db_fetch_one(q, {"tid": str(tenant_id), "uid": int(user_id), "oid": int(order_id)})
        return bool(row)

    @staticmethod
    async def set_archived(tenant_id: str, user_id: int, order_id: int, archived: bool) -> None:
        if archived:
            q = """
            INSERT INTO telegram_shop_orders_archive (tenant_id, user_id, order_id, archived_ts)
            VALUES (:tid, :uid, :oid, :ts)
            ON CONFLICT (tenant_id, user_id, order_id) DO UPDATE SET archived_ts = EXCLUDED.archived_ts
            """
            await db_execute(q, {"tid": str(tenant_id), "uid": int(user_id), "oid": int(order_id), "ts": int(time.time())})
        else:
            q = """
            DELETE FROM telegram_shop_orders_archive
            WHERE tenant_id = :tid AND user_id = :uid AND order_id = :oid
            """
            await db_execute(q, {"tid": str(tenant_id), "uid": int(user_id), "oid": int(order_id)})