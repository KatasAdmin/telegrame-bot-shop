from __future__ import annotations

import time
from typing import Any

from rent_platform.db.session import db_fetch_all, db_fetch_one, db_execute


class TelegramShopCartRepo:
    @staticmethod
    async def cart_set_qty(tenant_id: str, user_id: int, product_id: int, qty: int) -> None:
        qty = int(qty)
        if qty <= 0:
            await TelegramShopCartRepo.cart_delete_item(tenant_id, user_id, product_id)
            return

        q = """
        INSERT INTO telegram_shop_cart_items (tenant_id, user_id, product_id, qty, updated_ts)
        VALUES (:tid, :uid, :pid, :q, :ts)
        ON CONFLICT (tenant_id, user_id, product_id)
        DO UPDATE SET qty = EXCLUDED.qty, updated_ts = EXCLUDED.updated_ts
        """
        await db_execute(
            q,
            {
                "tid": tenant_id,
                "uid": int(user_id),
                "pid": int(product_id),
                "q": qty,
                "ts": int(time.time()),
            },
        )

    @staticmethod
    async def cart_inc(tenant_id: str, user_id: int, product_id: int, delta: int) -> int:
        """
        Increase/decrease qty by delta.
        If result <= 0 => item deleted.
        """
        delta = int(delta)
        q = """
        INSERT INTO telegram_shop_cart_items (tenant_id, user_id, product_id, qty, updated_ts)
        VALUES (:tid, :uid, :pid, 1, :ts)
        ON CONFLICT (tenant_id, user_id, product_id)
        DO UPDATE SET qty = GREATEST(0, telegram_shop_cart_items.qty + :d),
                      updated_ts = EXCLUDED.updated_ts
        RETURNING qty
        """
        row = await db_fetch_one(
            q,
            {
                "tid": tenant_id,
                "uid": int(user_id),
                "pid": int(product_id),
                "d": delta,
                "ts": int(time.time()),
            },
        )
        qty = int(row["qty"]) if row and row.get("qty") is not None else 0
        if qty <= 0:
            await TelegramShopCartRepo.cart_delete_item(tenant_id, user_id, product_id)
            return 0
        return qty

    @staticmethod
    async def cart_delete_item(tenant_id: str, user_id: int, product_id: int) -> None:
        q = """
        DELETE FROM telegram_shop_cart_items
        WHERE tenant_id = :tid AND user_id = :uid AND product_id = :pid
        """
        await db_execute(q, {"tid": tenant_id, "uid": int(user_id), "pid": int(product_id)})

    @staticmethod
    async def cart_clear(tenant_id: str, user_id: int) -> None:
        q = "DELETE FROM telegram_shop_cart_items WHERE tenant_id = :tid AND user_id = :uid"
        await db_execute(q, {"tid": tenant_id, "uid": int(user_id)})

    @staticmethod
    async def cart_list(tenant_id: str, user_id: int) -> list[dict[str, Any]]:
        """
        Join products and return BOTH prices:
        - base_price_kop: original price_kop
        - price_kop: effective price (promo if active else base)
        Also returns promo_active flag for UI.
        """
        now = int(time.time())
        q = """
        SELECT
            c.product_id,
            c.qty,
            p.name,
            COALESCE(p.price_kop, 0) AS base_price_kop,
            CASE
              WHEN COALESCE(p.promo_price_kop, 0) > 0
               AND (COALESCE(p.promo_until_ts, 0) = 0 OR COALESCE(p.promo_until_ts, 0) > :now)
              THEN COALESCE(p.promo_price_kop, 0)
              ELSE COALESCE(p.price_kop, 0)
            END AS price_kop,
            CASE
              WHEN COALESCE(p.promo_price_kop, 0) > 0
               AND (COALESCE(p.promo_until_ts, 0) = 0 OR COALESCE(p.promo_until_ts, 0) > :now)
              THEN true
              ELSE false
            END AS promo_active
        FROM telegram_shop_cart_items c
        JOIN telegram_shop_products p
          ON p.tenant_id = c.tenant_id AND p.id = c.product_id
        WHERE c.tenant_id = :tid AND c.user_id = :uid AND p.is_active = true
        ORDER BY c.updated_ts DESC
        """
        return await db_fetch_all(q, {"tid": tenant_id, "uid": int(user_id), "now": now}) or []