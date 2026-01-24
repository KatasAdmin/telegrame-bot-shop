from __future__ import annotations

import time
from typing import Any

from rent_platform.db.session import db_fetch_one, db_fetch_all, db_execute


class LunaShopRepo:
    """
    Зберігання: товари, кошик, замовлення
    Таблиці створиш міграцією (SQL нижче).
    """

    # ---------- products ----------
    @staticmethod
    async def list_products(tenant_id: str, limit: int = 50) -> list[dict[str, Any]]:
        q = """
        SELECT id, name, price_kop
        FROM luna_shop_products
        WHERE tenant_id = :tid AND is_active = true
        ORDER BY id DESC
        LIMIT :lim
        """
        return await db_fetch_all(q, {"tid": tenant_id, "lim": int(limit)})

    @staticmethod
    async def get_product(tenant_id: str, product_id: int) -> dict | None:
        q = """
        SELECT id, name, price_kop
        FROM luna_shop_products
        WHERE tenant_id = :tid AND id = :pid AND is_active = true
        """
        return await db_fetch_one(q, {"tid": tenant_id, "pid": int(product_id)})

    @staticmethod
    async def add_product(tenant_id: str, name: str, price_kop: int) -> int | None:
        q = """
        INSERT INTO luna_shop_products (tenant_id, name, price_kop, is_active, created_ts)
        VALUES (:tid, :n, :p, true, :ts)
        RETURNING id
        """
        row = await db_fetch_one(q, {
            "tid": tenant_id,
            "n": (name or "").strip()[:128],
            "p": int(price_kop),
            "ts": int(time.time()),
        })
        return int(row["id"]) if row and row.get("id") is not None else None

    # ---------- cart ----------
    @staticmethod
    async def cart_set_qty(tenant_id: str, user_id: int, product_id: int, qty: int) -> None:
        qty = int(qty)
        if qty <= 0:
            await LunaShopRepo.cart_delete_item(tenant_id, user_id, product_id)
            return

        q = """
        INSERT INTO luna_shop_cart_items (tenant_id, user_id, product_id, qty, updated_ts)
        VALUES (:tid, :uid, :pid, :q, :ts)
        ON CONFLICT (tenant_id, user_id, product_id)
        DO UPDATE SET qty = EXCLUDED.qty, updated_ts = EXCLUDED.updated_ts
        """
        await db_execute(q, {
            "tid": tenant_id,
            "uid": int(user_id),
            "pid": int(product_id),
            "q": qty,
            "ts": int(time.time()),
        })

    @staticmethod
    async def cart_inc(tenant_id: str, user_id: int, product_id: int, delta: int) -> int:
        delta = int(delta)
        q = """
        INSERT INTO luna_shop_cart_items (tenant_id, user_id, product_id, qty, updated_ts)
        VALUES (:tid, :uid, :pid, GREATEST(1, :d), :ts)
        ON CONFLICT (tenant_id, user_id, product_id)
        DO UPDATE SET qty = GREATEST(0, luna_shop_cart_items.qty + :d),
                      updated_ts = EXCLUDED.updated_ts
        RETURNING qty
        """
        row = await db_fetch_one(q, {
            "tid": tenant_id,
            "uid": int(user_id),
            "pid": int(product_id),
            "d": delta,
            "ts": int(time.time()),
        })
        qty = int(row["qty"]) if row and row.get("qty") is not None else 0
        if qty <= 0:
            await LunaShopRepo.cart_delete_item(tenant_id, user_id, product_id)
            return 0
        return qty

    @staticmethod
    async def cart_delete_item(tenant_id: str, user_id: int, product_id: int) -> None:
        q = """
        DELETE FROM luna_shop_cart_items
        WHERE tenant_id = :tid AND user_id = :uid AND product_id = :pid
        """
        await db_execute(q, {"tid": tenant_id, "uid": int(user_id), "pid": int(product_id)})

    @staticmethod
    async def cart_clear(tenant_id: str, user_id: int) -> None:
        q = "DELETE FROM luna_shop_cart_items WHERE tenant_id = :tid AND user_id = :uid"
        await db_execute(q, {"tid": tenant_id, "uid": int(user_id)})

    @staticmethod
    async def cart_list(tenant_id: str, user_id: int) -> list[dict]:
        q = """
        SELECT c.product_id, c.qty, p.name, p.price_kop
        FROM luna_shop_cart_items c
        JOIN luna_shop_products p
          ON p.tenant_id = c.tenant_id AND p.id = c.product_id
        WHERE c.tenant_id = :tid AND c.user_id = :uid AND p.is_active = true
        ORDER BY c.updated_ts DESC
        """
        return await db_fetch_all(q, {"tid": tenant_id, "uid": int(user_id)})

    # ---------- orders ----------
    @staticmethod
    async def create_order_from_cart(tenant_id: str, user_id: int) -> int | None:
        items = await LunaShopRepo.cart_list(tenant_id, user_id)
        if not items:
            return None

        total_kop = 0
        for it in items:
            total_kop += int(it["price_kop"]) * int(it["qty"])

        # створюємо order
        q1 = """
        INSERT INTO luna_shop_orders (tenant_id, user_id, status, total_kop, created_ts)
        VALUES (:tid, :uid, 'new', :t, :ts)
        RETURNING id
        """
        row = await db_fetch_one(q1, {
            "tid": tenant_id,
            "uid": int(user_id),
            "t": int(total_kop),
            "ts": int(time.time()),
        })
        if not row or row.get("id") is None:
            return None
        order_id = int(row["id"])

        # додаємо items
        q2 = """
        INSERT INTO luna_shop_order_items (order_id, product_id, name, price_kop, qty)
        VALUES (:oid, :pid, :n, :p, :q)
        """
        for it in items:
            await db_execute(q2, {
                "oid": order_id,
                "pid": int(it["product_id"]),
                "n": str(it["name"])[:128],
                "p": int(it["price_kop"]),
                "q": int(it["qty"]),
            })

        # чистимо кошик
        await LunaShopRepo.cart_clear(tenant_id, user_id)
        return order_id

    @staticmethod
    async def list_orders(tenant_id: str, user_id: int, limit: int = 20) -> list[dict]:
        q = """
        SELECT id, status, total_kop, created_ts
        FROM luna_shop_orders
        WHERE tenant_id = :tid AND user_id = :uid
        ORDER BY id DESC
        LIMIT :lim
        """
        return await db_fetch_all(q, {"tid": tenant_id, "uid": int(user_id), "lim": int(limit)})