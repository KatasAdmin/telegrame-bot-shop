# -*- coding: utf-8 -*-
from __future__ import annotations

import time

from rent_platform.db.session import db_fetch_one, db_execute


class TelegramShopOrdersAdminArchiveRepo:
    @staticmethod
    async def is_archived(tenant_id: str, order_id: int) -> bool:
        q = """
        SELECT 1
        FROM telegram_shop_orders_admin_archive
        WHERE tenant_id = :tid AND order_id = :oid
        LIMIT 1
        """
        row = await db_fetch_one(q, {"tid": str(tenant_id), "oid": int(order_id)})
        return bool(row)

    @staticmethod
    async def toggle(tenant_id: str, order_id: int) -> bool:
        """
        returns True if archived now, False if unarchived now
        """
        if await TelegramShopOrdersAdminArchiveRepo.is_archived(tenant_id, order_id):
            q = """
            DELETE FROM telegram_shop_orders_admin_archive
            WHERE tenant_id = :tid AND order_id = :oid
            """
            await db_execute(q, {"tid": str(tenant_id), "oid": int(order_id)})
            return False

        q = """
        INSERT INTO telegram_shop_orders_admin_archive (tenant_id, order_id, archived_ts)
        VALUES (:tid, :oid, :ts)
        ON CONFLICT (tenant_id, order_id) DO UPDATE SET archived_ts = EXCLUDED.archived_ts
        """
        await db_execute(q, {"tid": str(tenant_id), "oid": int(order_id), "ts": int(time.time())})
        return True