# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from typing import Any, Iterable

from rent_platform.db.session import db_fetch_all, db_fetch_one, db_execute
from rent_platform.modules.telegram_shop.repo.cart import TelegramShopCartRepo


class TelegramShopOrdersRepo:
    """
    Orders repository:
      - create order from cart (snapshot items + qty + sku snapshot when available)
      - user orders list / detail
      - user archive (telegram_shop_orders_archive) support
      - order items list (sku optional)
      - bulk helpers for admin exports (no N+1)
    """

    # -----------------------------
    # Internals
    # -----------------------------
    @staticmethod
    def _now_ts() -> int:
        return int(time.time())

    @staticmethod
    def _to_int(v: Any, default: int = 0) -> int:
        try:
            return int(v)
        except Exception:
            return default

    @staticmethod
    def _uniq_ints(xs: Iterable[Any]) -> list[int]:
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

    @staticmethod
    async def _try_begin() -> bool:
        try:
            await db_execute("BEGIN")
            return True
        except Exception:
            return False

    @staticmethod
    async def _try_commit() -> None:
        try:
            await db_execute("COMMIT")
        except Exception:
            pass

    @staticmethod
    async def _try_rollback() -> None:
        try:
            await db_execute("ROLLBACK")
        except Exception:
            pass

    # -----------------------------
    # Core: create order from cart
    # -----------------------------
    @staticmethod
    async def create_order_from_cart(tenant_id: str, user_id: int) -> int | None:
        """
        Best-effort atomic flow:
          1) read cart items (already contains effective price_kop)
          2) compute total
          3) insert order
          4) snapshot items (+ sku snapshot if column exists)
          5) clear cart
        """
        items = await TelegramShopCartRepo.cart_list(tenant_id, user_id)
        if not items:
            return None

        total_kop = 0
        for it in items:
            price_kop = TelegramShopOrdersRepo._to_int(it.get("price_kop"), 0)
            qty = TelegramShopOrdersRepo._to_int(it.get("qty"), 0)
            if qty > 0 and price_kop > 0:
                total_kop += price_kop * qty

        if total_kop <= 0:
            return None

        # sku map (ONE query for all pids)
        pids = TelegramShopOrdersRepo._uniq_ints(it.get("product_id") for it in items)
        sku_map: dict[int, str] = {}
        if pids:
            qsku_many = """
            SELECT id, COALESCE(sku,'') AS sku
            FROM telegram_shop_products
            WHERE tenant_id = :tid AND id = ANY(:pids)
            """
            rows_sku = await db_fetch_all(qsku_many, {"tid": tenant_id, "pids": pids}) or []
            for r in rows_sku:
                pid = TelegramShopOrdersRepo._to_int(r.get("id"), 0)
                if pid > 0:
                    sku_map[pid] = str(r.get("sku") or "")[:64]

        q_order_ins = """
        INSERT INTO telegram_shop_orders (tenant_id, user_id, status, total_kop, created_ts)
        VALUES (:tid, :uid, 'new', :t, :ts)
        RETURNING id
        """

        # sku column may not exist -> fallback
        q_item_ins_with_sku = """
        INSERT INTO telegram_shop_order_items (order_id, product_id, name, price_kop, qty, sku)
        VALUES (:oid, :pid, :n, :p, :q, :sku)
        """
        q_item_ins = """
        INSERT INTO telegram_shop_order_items (order_id, product_id, name, price_kop, qty)
        VALUES (:oid, :pid, :n, :p, :q)
        """

        ts = TelegramShopOrdersRepo._now_ts()

        began = await TelegramShopOrdersRepo._try_begin()
        try:
            row = await db_fetch_one(
                q_order_ins,
                {"tid": tenant_id, "uid": int(user_id), "t": int(total_kop), "ts": int(ts)},
            )
            if not row or row.get("id") is None:
                if began:
                    await TelegramShopOrdersRepo._try_rollback()
                return None

            order_id = int(row["id"])

            for it in items:
                pid = TelegramShopOrdersRepo._to_int(it.get("product_id"), 0)
                qty = TelegramShopOrdersRepo._to_int(it.get("qty"), 0)
                price_kop = TelegramShopOrdersRepo._to_int(it.get("price_kop"), 0)
                if pid <= 0 or qty <= 0 or price_kop <= 0:
                    continue

                payload = {
                    "oid": order_id,
                    "pid": pid,
                    "n": str(it.get("name") or "")[:128],
                    "p": int(price_kop),
                    "q": int(qty),
                    "sku": sku_map.get(pid, "")[:64],
                }

                try:
                    await db_execute(q_item_ins_with_sku, payload)
                except Exception:
                    await db_execute(q_item_ins, payload)

            await TelegramShopCartRepo.cart_clear(tenant_id, user_id)

            if began:
                await TelegramShopOrdersRepo._try_commit()

            return order_id

        except Exception:
            if began:
                await TelegramShopOrdersRepo._try_rollback()
            return None

    # -----------------------------
    # User archive (telegram_shop_orders_archive)
    # -----------------------------
    @staticmethod
    async def is_archived(tenant_id: str, order_id: int) -> bool:
        """
        User archive flag (NOT admin archive).
        Requires table telegram_shop_orders_archive(tenant_id, order_id, archived_ts?).
        """
        q = """
        SELECT 1
        FROM telegram_shop_orders_archive a
        WHERE a.tenant_id = :tid AND a.order_id = :oid
        LIMIT 1
        """
        try:
            row = await db_fetch_one(q, {"tid": tenant_id, "oid": int(order_id)})
            return bool(row)
        except Exception:
            # if table doesn't exist yet
            return False

    @staticmethod
    async def toggle_archive(tenant_id: str, order_id: int) -> None:
        """
        Toggle user archive (best-effort, if table exists).
        """
        # delete if exists
        q_del = """
        DELETE FROM telegram_shop_orders_archive
        WHERE tenant_id = :tid AND order_id = :oid
        """
        # insert if not exists
        q_ins = """
        INSERT INTO telegram_shop_orders_archive (tenant_id, order_id, archived_ts)
        VALUES (:tid, :oid, :ts)
        ON CONFLICT (tenant_id, order_id) DO NOTHING
        """
        try:
            exists = await TelegramShopOrdersRepo.is_archived(tenant_id, int(order_id))
            if exists:
                await db_execute(q_del, {"tid": tenant_id, "oid": int(order_id)})
            else:
                await db_execute(q_ins, {"tid": tenant_id, "oid": int(order_id), "ts": TelegramShopOrdersRepo._now_ts()})
        except Exception:
            # if table doesn't exist or constraint differs -> ignore
            return

    # -----------------------------
    # User orders
    # -----------------------------
    @staticmethod
    async def list_orders(
        tenant_id: str,
        user_id: int,
        limit: int = 20,
        *,
        archived: bool = False,
    ) -> list[dict[str, Any]]:
        """
        archived=False -> non-archived (default)
        archived=True  -> archived list (if orders_archive table exists; else returns normal list)
        """
        base = """
        SELECT o.id, o.status, o.total_kop, o.created_ts
        FROM telegram_shop_orders o
        WHERE o.tenant_id = :tid AND o.user_id = :uid
        """

        if archived:
            q = (
                base
                + """
                  AND EXISTS (
                      SELECT 1 FROM telegram_shop_orders_archive a
                      WHERE a.tenant_id = o.tenant_id AND a.order_id = o.id
                  )
                ORDER BY o.id DESC
                LIMIT :lim
                """
            )
        else:
            q = (
                base
                + """
                  AND NOT EXISTS (
                      SELECT 1 FROM telegram_shop_orders_archive a
                      WHERE a.tenant_id = o.tenant_id AND a.order_id = o.id
                  )
                ORDER BY o.id DESC
                LIMIT :lim
                """
            )

        try:
            return await db_fetch_all(q, {"tid": tenant_id, "uid": int(user_id), "lim": int(limit)}) or []
        except Exception:
            # if archive table doesn't exist -> fallback to simple list
            q2 = """
            SELECT id, status, total_kop, created_ts
            FROM telegram_shop_orders
            WHERE tenant_id = :tid AND user_id = :uid
            ORDER BY id DESC
            LIMIT :lim
            """
            return await db_fetch_all(q2, {"tid": tenant_id, "uid": int(user_id), "lim": int(limit)}) or []

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
    # Items snapshot
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

    # -----------------------------
    # Admin helpers (no N+1)
    # -----------------------------
    @staticmethod
    async def list_new_orders_headers_excluding_admin_archive(tenant_id: str, limit_orders: int = 200) -> list[dict[str, Any]]:
        """
        Headers of NEW orders that are NOT in admin archive.
        Useful for exports.
        """
        q = """
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
        return await db_fetch_all(q, {"tid": tenant_id, "lim": int(limit_orders)}) or []

    @staticmethod
    async def list_items_for_tenant_new_orders(tenant_id: str, limit_orders: int = 200) -> list[dict[str, Any]]:
        """
        Flattened list for exports:
          - loads NEW order headers (not in admin archive)
          - loads ALL items for those orders in one query
          - injects user_id + created_ts into each item row
        """
        orders = await TelegramShopOrdersRepo.list_new_orders_headers_excluding_admin_archive(tenant_id, limit_orders=limit_orders)
        if not orders:
            return []

        order_ids = [int(o["id"]) for o in orders if TelegramShopOrdersRepo._to_int(o.get("id")) > 0]
        items = await TelegramShopOrdersRepo.list_items_for_orders(order_ids)

        hdr = {int(o["id"]): o for o in orders if TelegramShopOrdersRepo._to_int(o.get("id")) > 0}

        out: list[dict[str, Any]] = []
        for it in items:
            oid = TelegramShopOrdersRepo._to_int(it.get("order_id"), 0)
            h = hdr.get(oid) or {}
            row = dict(it)
            row["user_id"] = TelegramShopOrdersRepo._to_int(h.get("user_id"), 0)
            row["created_ts"] = TelegramShopOrdersRepo._to_int(h.get("created_ts"), 0)
            out.append(row)

        return out