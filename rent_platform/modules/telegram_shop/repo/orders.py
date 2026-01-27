from __future__ import annotations

import time
from typing import Any

from rent_platform.db.session import db_fetch_all, db_fetch_one, db_execute
from rent_platform.modules.telegram_shop.repo.cart import TelegramShopCartRepo


class TelegramShopOrdersRepo:
    @staticmethod
    async def create_order_from_cart(tenant_id: str, user_id: int) -> int | None:
        items = await TelegramShopCartRepo.cart_list(tenant_id, user_id)
        if not items:
            return None

        total_kop = 0
        for it in items:
            price_kop = int(it.get("price_kop") or 0)
            total_kop += price_kop * int(it.get("qty") or 0)

        # 1) create order
        q1 = """
        INSERT INTO telegram_shop_orders (tenant_id, user_id, status, total_kop, created_ts)
        VALUES (:tid, :uid, 'new', :t, :ts)
        RETURNING id
        """
        row = await db_fetch_one(
            q1,
            {"tid": tenant_id, "uid": int(user_id), "t": int(total_kop), "ts": int(time.time())},
        )
        if not row or row.get("id") is None:
            return None
        order_id = int(row["id"])

        # 2) order items snapshot (+ sku snapshot)
        # IMPORTANT: requires telegram_shop_order_items.sku column (migration 4.1)
        qsku = """
        SELECT COALESCE(sku,'') AS sku
        FROM telegram_shop_products
        WHERE tenant_id = :tid AND id = :pid
        LIMIT 1
        """

        q2 = """
        INSERT INTO telegram_shop_order_items (order_id, product_id, name, price_kop, qty, sku)
        VALUES (:oid, :pid, :n, :p, :q, :sku)
        """

        for it in items:
            pid = int(it["product_id"])
            row_sku = await db_fetch_one(qsku, {"tid": tenant_id, "pid": pid}) or {}
            sku = str(row_sku.get("sku") or "")[:64]

            await db_execute(
                q2,
                {
                    "oid": order_id,
                    "pid": pid,
                    "n": str(it["name"])[:128],
                    "p": int(it.get("price_kop") or 0),
                    "q": int(it.get("qty") or 0),
                    "sku": sku,
                },
            )

        # 3) clear cart
        await TelegramShopCartRepo.cart_clear(tenant_id, user_id)
        return order_id

    @staticmethod
    async def list_orders(tenant_id: str, user_id: int, limit: int = 20) -> list[dict[str, Any]]:
        q = """
        SELECT id, status, total_kop, created_ts
        FROM telegram_shop_orders
        WHERE tenant_id = :tid AND user_id = :uid
        ORDER BY id DESC
        LIMIT :lim
        """
        return await db_fetch_all(q, {"tid": tenant_id, "uid": int(user_id), "lim": int(limit)}) or []

    @staticmethod
    async def get_order(tenant_id: str, order_id: int) -> dict[str, Any] | None:
        q = """
        SELECT id, tenant_id, user_id, status, total_kop, created_ts
        FROM telegram_shop_orders
        WHERE tenant_id = :tid AND id = :oid
        """
        return await db_fetch_one(q, {"tid": tenant_id, "oid": int(order_id)})

    @staticmethod
    async def list_order_items(order_id: int) -> list[dict[str, Any]]:
        # sku може бути відсутній, якщо міграцію ще не накатили
        # але після 4.1 він буде і все ок
        q = """
        SELECT id, order_id, product_id, name, price_kop, qty, COALESCE(sku,'') AS sku
        FROM telegram_shop_order_items
        WHERE order_id = :oid
        ORDER BY id ASC
        """
        return await db_fetch_all(q, {"oid": int(order_id)}) or []