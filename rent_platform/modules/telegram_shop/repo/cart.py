# -*- coding: utf-8 -*-
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
        If result <= 0 => item deleted and returns 0.

        IMPORTANT:
        - If item doesn't exist, initial qty becomes max(delta, 0), not always 1.
        """
        delta = int(delta)
        if delta == 0:
            # nothing to do; just return current qty
            cur = await TelegramShopCartRepo.cart_get_qty(tenant_id, user_id, product_id)
            return int(cur or 0)

        # If item absent: insert qty = GREATEST(delta, 0)
        # If exists: qty = qty + delta
        q = """
        INSERT INTO telegram_shop_cart_items (tenant_id, user_id, product_id, qty, updated_ts)
        VALUES (:tid, :uid, :pid, GREATEST(:d, 0), :ts)
        ON CONFLICT (tenant_id, user_id, product_id)
        DO UPDATE SET
            qty = telegram_shop_cart_items.qty + :d,
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
    async def cart_get_qty(tenant_id: str, user_id: int, product_id: int) -> int:
        q = """
        SELECT qty
        FROM telegram_shop_cart_items
        WHERE tenant_id = :tid AND user_id = :uid AND product_id = :pid
        LIMIT 1
        """
        row = await db_fetch_one(q, {"tid": tenant_id, "uid": int(user_id), "pid": int(product_id)}) or {}
        return int(row.get("qty") or 0)

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
    async def cart_list(tenant_id: str, user_id: int, *, include_sku: bool = False) -> list[dict[str, Any]]:
        """
        Join products and return:
          - base_price_kop (звичайна)
          - price_kop (effective: promo if active, else base)
          - optional sku
        """
        now = int(time.time())

        sku_select = ", COALESCE(p.sku,'') AS sku" if include_sku else ""
        q = f"""
        SELECT
            c.product_id,
            c.qty,
            p.name
            {sku_select},
            COALESCE(p.price_kop, 0) AS base_price_kop,
            CASE
              WHEN COALESCE(p.promo_price_kop, 0) > 0
               AND (COALESCE(p.promo_until_ts, 0) = 0 OR COALESCE(p.promo_until_ts, 0) > :now)
              THEN COALESCE(p.promo_price_kop, 0)
              ELSE COALESCE(p.price_kop, 0)
            END AS price_kop
        FROM telegram_shop_cart_items c
        JOIN telegram_shop_products p
          ON p.tenant_id = c.tenant_id AND p.id = c.product_id
        WHERE c.tenant_id = :tid
          AND c.user_id = :uid
          AND p.is_active = true
        ORDER BY c.updated_ts DESC
        """
        return await db_fetch_all(q, {"tid": tenant_id, "uid": int(user_id), "now": now}) or []

    @staticmethod
    async def cart_get_total_kop(tenant_id: str, user_id: int) -> int:
        """
        Total using effective (promo-aware) price in ONE query.
        """
        now = int(time.time())
        q = """
        SELECT
          COALESCE(SUM(
            c.qty * (
              CASE
                WHEN COALESCE(p.promo_price_kop, 0) > 0
                 AND (COALESCE(p.promo_until_ts, 0) = 0 OR COALESCE(p.promo_until_ts, 0) > :now)
                THEN COALESCE(p.promo_price_kop, 0)
                ELSE COALESCE(p.price_kop, 0)
              END
            )
          ), 0) AS total_kop
        FROM telegram_shop_cart_items c
        JOIN telegram_shop_products p
          ON p.tenant_id = c.tenant_id AND p.id = c.product_id
        WHERE c.tenant_id = :tid
          AND c.user_id = :uid
          AND p.is_active = true
        """
        row = await db_fetch_one(q, {"tid": tenant_id, "uid": int(user_id), "now": now}) or {}
        return int(row.get("total_kop") or 0)