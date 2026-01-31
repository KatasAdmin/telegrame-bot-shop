# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from typing import Any, Iterable

from rent_platform.db.session import db_fetch_all, db_fetch_one, db_execute
from rent_platform.modules.telegram_shop.repo.cart import TelegramShopCartRepo


class TelegramShopOrdersRepo:
    """
    Orders repository:
      - creates order from cart
      - order list/details
      - order items list (with SKU snapshot when available)
      - bulk helpers for admin exports (no N+1)
    """

    # -----------------------------
    # Internals
    # -----------------------------
    @staticmethod
    def _now_ts() -> int:
        return int(time.time())

    @staticmethod
    def _uniq_ints(xs: Iterable[int]) -> list[int]:
        out: list[int] = []
        seen: set[int] = set()
        for x in xs:
            try:
                v = int(x)
            except Exception:
                continue
            if v <= 0 or v in seen:
                continue
            seen.add(v)
            out.append(v)
        return out

    # -----------------------------
    # Core: create order from cart
    # -----------------------------
    @staticmethod
    async def create_order_from_cart(tenant_id: str, user_id: int) -> int | None:
        """
        Atomically:
          1) read cart items
          2) compute total
          3) insert order
          4) snapshot items into telegram_shop_order_items (+ sku snapshot if column exists)
          5) clear cart
        """
        items = await TelegramShopCartRepo.cart_list(tenant_id, user_id)
        if not items:
            return None

        # total
        total_kop = 0
        for it in items:
            price_kop = int(it.get("price_kop") or 0)
            qty = int(it.get("qty") or 0)
            if qty <= 0:
                continue
            total_kop += price_kop * qty

        if total_kop <= 0:
            return None

        # sku map (ONE query for all pids)
        pids = TelegramShopOrdersRepo._uniq_ints(int(it.get("product_id") or 0) for it in items)
        sku_map: dict[int, str] = {}
        if pids:
            qsku_many = """
            SELECT id, COALESCE(sku,'') AS sku
            FROM telegram_shop_products
            WHERE tenant_id = :tid AND id = ANY(:pids)
            """
            rows_sku = await db_fetch_all(qsku_many, {"tid": tenant_id, "pids": pids}) or []
            sku_map = {int(r["id"]): str(r.get("sku") or "")[:64] for r in rows_sku if int(r.get("id") or 0) > 0}

        # queries
        q_order_ins = """
        INSERT INTO telegram_shop_orders (tenant_id, user_id, status, total_kop, created_ts)
        VALUES (:tid, :uid, 'new', :t, :ts)
        RETURNING id
        """

        # NOTE: sku column may not exist -> fallback
        q_item_ins_with_sku = """
        INSERT INTO telegram_shop_order_items (order_id, product_id, name, price_kop, qty, sku)
        VALUES (:oid, :pid, :n, :p, :q, :sku)
        """
        q_item_ins = """
        INSERT INTO telegram_shop_order_items (order_id, product_id, name, price_kop, qty)
        VALUES (:oid, :pid, :n, :p, :q)
        """

        ts = TelegramShopOrdersRepo._now_ts()

        # --- best-effort transaction ---
        # If your db layer supports manual transactions, this will be atomic.
        # If not, it still works correctly (cart clears only at the end).
        began = False
        try:
            await db_execute("BEGIN")
            began = True
        except Exception:
            began = False

        try:
            row = await db_fetch_one(q_order_ins, {"tid": tenant_id, "uid": int(user_id), "t": int(total_kop), "ts": ts})
            if not row or row.get("id") is None:
                if began:
                    try:
                        await db_execute("ROLLBACK")
                    except Exception:
                        pass
                return None

            order_id = int(row["id"])

            # insert items
            for it in items:
                pid = int(it.get("product_id") or 0)
                if pid <= 0:
                    continue

                qty = int(it.get("qty") or 0)
                if qty <= 0:
                    continue

                payload = {
                    "oid": order_id,
                    "pid": pid,
                    "n": str(it.get("name") or "")[:128],
                    "p": int(it.get("price_kop") or 0),
                    "q": qty,
                    "sku": sku_map.get(pid, "")[:64],
                }

                try:
                    await db_execute(q_item_ins_with_sku, payload)
                except Exception:
                    # column sku might not exist yet
                    await db_execute(q_item_ins, payload)

            # clear cart only after successful inserts
            await TelegramShopCartRepo.cart_clear(tenant_id, user_id)

            if began:
                try:
                    await db_execute("COMMIT")
                except Exception:
                    pass

            return order_id

        except Exception:
            if began:
                try:
                    await db_execute("ROLLBACK")
                except Exception:
                    pass
            # do NOT clear cart on error
            return None

    # -----------------------------
    # User orders
    # -----------------------------
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
        LIMIT 1
        """
        return await db_fetch_one(q, {"tid": tenant_id, "oid": int(order_id)})

    # -----------------------------
    # Items
    # -----------------------------
    @staticmethod
    async def list_order_items(order_id: int) -> list[dict[str, Any]]:
        """
        Returns items snapshot.
        sku column may not exist -> fallback without sku.
        """
        q_with_sku = """
        SELECT id, order_id, product_id, name, price_kop, qty, sku
        FROM telegram_shop_order_items
        WHERE order_id = :oid
        ORDER BY id ASC
        """
        q = """
        SELECT id, order_id, product_id, name, price_kop, qty
        FROM telegram_shop_order_items
        WHERE order_id = :oid
        ORDER BY id ASC
        """
        try:
            return await db_fetch_all(q_with_sku, {"oid": int(order_id)}) or []
        except Exception:
            return await db_fetch_all(q, {"oid": int(order_id)}) or []

    @staticmethod
    async def list_items_for_orders(order_ids: list[int]) -> list[dict[str, Any]]:
        """
        Bulk load items for many orders (for exports/admin).
        No N+1.

        Returns rows:
          order_id, product_id, name, qty, price_kop, sku? (if exists)
        """
        oids = TelegramShopOrdersRepo._uniq_ints(order_ids)
        if not oids:
            return []

        q_with_sku = """
        SELECT
          order_id,
          product_id,
          name,
          qty,
          price_kop,
          COALESCE(sku,'') AS sku
        FROM telegram_shop_order_items
        WHERE order_id = ANY(:oids)
        ORDER BY order_id ASC, id ASC
        """
        q = """
        SELECT
          order_id,
          product_id,
          name,
          qty,
          price_kop
        FROM telegram_shop_order_items
        WHERE order_id = ANY(:oids)
        ORDER BY order_id ASC, id ASC
        """
        try:
            return await db_fetch_all(q_with_sku, {"oids": oids}) or []
        except Exception:
            return await db_fetch_all(q, {"oids": oids}) or []

    @staticmethod
    async def list_items_for_tenant_new_orders(tenant_id: str, limit_orders: int = 200) -> list[dict[str, Any]]:
        """
        Helper for exporting 'new' orders picklist without N+1:
          - loads order headers (new + not in admin archive) up to limit
          - loads all items in one query via list_items_for_orders
          - returns flattened list with order header fields inside each item row
        """
        q_orders = """
        SELECT o.id, o.user_id, o.created_ts
        FROM telegram_shop_orders o
        WHERE o.tenant_id = :tid
          AND o.status = 'new'
          AND NOT EXISTS (
              SELECT 1
              FROM telegram_shop_orders_admin_archive a
              WHERE a.tenant_id = o.tenant_id AND a.order_id = o.id
          )
        ORDER BY o.id ASC
        LIMIT :lim
        """
        orders = await db_fetch_all(q_orders, {"tid": tenant_id, "lim": int(limit_orders)}) or []
        if not orders:
            return []

        order_ids = [int(o["id"]) for o in orders if int(o.get("id") or 0) > 0]
        items = await TelegramShopOrdersRepo.list_items_for_orders(order_ids)

        # map headers
        hdr = {int(o["id"]): o for o in orders if int(o.get("id") or 0) > 0}

        out: list[dict[str, Any]] = []
        for it in items:
            oid = int(it.get("order_id") or 0)
            h = hdr.get(oid) or {}
            row = dict(it)
            row["user_id"] = int(h.get("user_id") or 0)
            row["created_ts"] = int(h.get("created_ts") or 0)
            out.append(row)

        return out