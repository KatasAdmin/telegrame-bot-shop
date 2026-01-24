from __future__ import annotations

import time
from typing import Any

from rent_platform.db.session import db_fetch_one, db_fetch_all, db_execute


class LunaShopRepo:
    """
    Зберігання: товари, кошик, замовлення
    + Хіти/Акції (is_hit, promo_price_kop, promo_until_ts)
    """

    # ---------- helpers ----------
    @staticmethod
    def _now_ts() -> int:
        return int(time.time())

    @staticmethod
    def _effective_price_kop(row: dict, now_ts: int | None = None) -> int:
        """
        Повертає актуальну ціну:
        - якщо promo_until_ts > now і promo_price_kop > 0 -> promo_price_kop
        - інакше -> price_kop
        """
        now_ts = int(now_ts or LunaShopRepo._now_ts())
        price = int(row.get("price_kop") or 0)
        promo_price = int(row.get("promo_price_kop") or 0)
        promo_until = int(row.get("promo_until_ts") or 0)

        if promo_price > 0 and promo_until > now_ts:
            return promo_price
        return price

    # ---------- products ----------
    @staticmethod
    async def list_products(tenant_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """
        Каталог: всі активні товари.
        Повертаємо також computed: effective_price_kop, has_promo
        """
        q = """
        SELECT id, tenant_id, name, price_kop, is_active,
               COALESCE(is_hit, false) AS is_hit,
               COALESCE(promo_price_kop, 0) AS promo_price_kop,
               COALESCE(promo_until_ts, 0) AS promo_until_ts
        FROM luna_shop_products
        WHERE tenant_id = :tid AND is_active = true
        ORDER BY id DESC
        LIMIT :lim
        """
        rows = await db_fetch_all(q, {"tid": tenant_id, "lim": int(limit)}) or []
        now_ts = LunaShopRepo._now_ts()

        out: list[dict[str, Any]] = []
        for r in rows:
            eff = LunaShopRepo._effective_price_kop(r, now_ts)
            out.append({
                "id": int(r["id"]),
                "name": r["name"],
                "price_kop": int(r.get("price_kop") or 0),
                "is_hit": bool(r.get("is_hit")),
                "promo_price_kop": int(r.get("promo_price_kop") or 0),
                "promo_until_ts": int(r.get("promo_until_ts") or 0),
                "effective_price_kop": int(eff),
                "has_promo": bool(int(r.get("promo_price_kop") or 0) > 0 and int(r.get("promo_until_ts") or 0) > now_ts),
            })
        return out

    @staticmethod
    async def list_hits(tenant_id: str, limit: int = 50) -> list[dict[str, Any]]:
        q = """
        SELECT id, tenant_id, name, price_kop, is_active,
               COALESCE(is_hit, false) AS is_hit,
               COALESCE(promo_price_kop, 0) AS promo_price_kop,
               COALESCE(promo_until_ts, 0) AS promo_until_ts
        FROM luna_shop_products
        WHERE tenant_id = :tid AND is_active = true AND COALESCE(is_hit, false) = true
        ORDER BY id DESC
        LIMIT :lim
        """
        rows = await db_fetch_all(q, {"tid": tenant_id, "lim": int(limit)}) or []
        now_ts = LunaShopRepo._now_ts()

        out: list[dict[str, Any]] = []
        for r in rows:
            eff = LunaShopRepo._effective_price_kop(r, now_ts)
            out.append({
                "id": int(r["id"]),
                "name": r["name"],
                "price_kop": int(r.get("price_kop") or 0),
                "is_hit": True,
                "promo_price_kop": int(r.get("promo_price_kop") or 0),
                "promo_until_ts": int(r.get("promo_until_ts") or 0),
                "effective_price_kop": int(eff),
                "has_promo": bool(int(r.get("promo_price_kop") or 0) > 0 and int(r.get("promo_until_ts") or 0) > now_ts),
            })
        return out

    @staticmethod
    async def list_promos(tenant_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """
        Акції: promo_price_kop > 0 і promo_until_ts ще не минув.
        """
        now_ts = LunaShopRepo._now_ts()
        q = """
        SELECT id, tenant_id, name, price_kop, is_active,
               COALESCE(is_hit, false) AS is_hit,
               COALESCE(promo_price_kop, 0) AS promo_price_kop,
               COALESCE(promo_until_ts, 0) AS promo_until_ts
        FROM luna_shop_products
        WHERE tenant_id = :tid AND is_active = true
          AND COALESCE(promo_price_kop, 0) > 0
          AND COALESCE(promo_until_ts, 0) > :now
        ORDER BY promo_until_ts ASC, id DESC
        LIMIT :lim
        """
        rows = await db_fetch_all(q, {"tid": tenant_id, "now": int(now_ts), "lim": int(limit)}) or []

        out: list[dict[str, Any]] = []
        for r in rows:
            eff = LunaShopRepo._effective_price_kop(r, now_ts)
            out.append({
                "id": int(r["id"]),
                "name": r["name"],
                "price_kop": int(r.get("price_kop") or 0),
                "is_hit": bool(r.get("is_hit")),
                "promo_price_kop": int(r.get("promo_price_kop") or 0),
                "promo_until_ts": int(r.get("promo_until_ts") or 0),
                "effective_price_kop": int(eff),
                "has_promo": True,
            })
        return out

    @staticmethod
    async def get_product(tenant_id: str, product_id: int) -> dict | None:
        q = """
        SELECT id, tenant_id, name, price_kop, is_active,
               COALESCE(is_hit, false) AS is_hit,
               COALESCE(promo_price_kop, 0) AS promo_price_kop,
               COALESCE(promo_until_ts, 0) AS promo_until_ts
        FROM luna_shop_products
        WHERE tenant_id = :tid AND id = :pid AND is_active = true
        """
        r = await db_fetch_one(q, {"tid": tenant_id, "pid": int(product_id)})
        if not r:
            return None

        now_ts = LunaShopRepo._now_ts()
        eff = LunaShopRepo._effective_price_kop(r, now_ts)
        return {
            "id": int(r["id"]),
            "name": r["name"],
            "price_kop": int(r.get("price_kop") or 0),
            "is_hit": bool(r.get("is_hit")),
            "promo_price_kop": int(r.get("promo_price_kop") or 0),
            "promo_until_ts": int(r.get("promo_until_ts") or 0),
            "effective_price_kop": int(eff),
            "has_promo": bool(int(r.get("promo_price_kop") or 0) > 0 and int(r.get("promo_until_ts") or 0) > now_ts),
        }

    @staticmethod
    async def add_product(tenant_id: str, name: str, price_kop: int) -> int | None:
        q = """
        INSERT INTO luna_shop_products (tenant_id, name, price_kop, is_active, created_ts, is_hit, promo_price_kop, promo_until_ts)
        VALUES (:tid, :n, :p, true, :ts, false, 0, 0)
        RETURNING id
        """
        row = await db_fetch_one(q, {
            "tid": tenant_id,
            "n": (name or "").strip()[:128],
            "p": int(price_kop),
            "ts": int(time.time()),
        })
        return int(row["id"]) if row and row.get("id") is not None else None

    # --- admin updates for hits/promos ---
    @staticmethod
    async def set_hit(tenant_id: str, product_id: int, is_hit: bool) -> bool:
        q = """
        UPDATE luna_shop_products
        SET is_hit = :h
        WHERE tenant_id = :tid AND id = :pid
        """
        res = await db_execute(q, {"tid": tenant_id, "pid": int(product_id), "h": bool(is_hit)})
        try:
            return int(res or 0) > 0
        except Exception:
            # якщо db_execute не повертає rowcount — вважаємо ок
            return True

    @staticmethod
    async def set_promo(tenant_id: str, product_id: int, promo_price_kop: int, promo_until_ts: int) -> bool:
        q = """
        UPDATE luna_shop_products
        SET promo_price_kop = :pp,
            promo_until_ts = :pu
        WHERE tenant_id = :tid AND id = :pid
        """
        res = await db_execute(q, {
            "tid": tenant_id,
            "pid": int(product_id),
            "pp": int(promo_price_kop),
            "pu": int(promo_until_ts),
        })
        try:
            return int(res or 0) > 0
        except Exception:
            return True

    @staticmethod
    async def clear_promo(tenant_id: str, product_id: int) -> bool:
        q = """
        UPDATE luna_shop_products
        SET promo_price_kop = 0,
            promo_until_ts = 0
        WHERE tenant_id = :tid AND id = :pid
        """
        res = await db_execute(q, {"tid": tenant_id, "pid": int(product_id)})
        try:
            return int(res or 0) > 0
        except Exception:
            return True

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
        """
        В кошику теж враховуємо акційну ціну (якщо активна).
        Повертаємо effective_price_kop.
        """
        q = """
        SELECT c.product_id, c.qty,
               p.name,
               p.price_kop,
               COALESCE(p.promo_price_kop, 0) AS promo_price_kop,
               COALESCE(p.promo_until_ts, 0) AS promo_until_ts
        FROM luna_shop_cart_items c
        JOIN luna_shop_products p
          ON p.tenant_id = c.tenant_id AND p.id = c.product_id
        WHERE c.tenant_id = :tid AND c.user_id = :uid AND p.is_active = true
        ORDER BY c.updated_ts DESC
        """
        rows = await db_fetch_all(q, {"tid": tenant_id, "uid": int(user_id)}) or []
        now_ts = LunaShopRepo._now_ts()

        out: list[dict] = []
        for r in rows:
            eff = LunaShopRepo._effective_price_kop(r, now_ts)
            out.append({
                "product_id": int(r["product_id"]),
                "qty": int(r["qty"]),
                "name": r["name"],
                "price_kop": int(r.get("price_kop") or 0),
                "promo_price_kop": int(r.get("promo_price_kop") or 0),
                "promo_until_ts": int(r.get("promo_until_ts") or 0),
                "effective_price_kop": int(eff),
                "has_promo": bool(int(r.get("promo_price_kop") or 0) > 0 and int(r.get("promo_until_ts") or 0) > now_ts),
            })
        return out

    # ---------- orders ----------
    @staticmethod
    async def create_order_from_cart(tenant_id: str, user_id: int) -> int | None:
        items = await LunaShopRepo.cart_list(tenant_id, user_id)
        if not items:
            return None

        total_kop = 0
        for it in items:
            total_kop += int(it["effective_price_kop"]) * int(it["qty"])

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

        # додаємо items (фіксуємо ЦІНУ НА МОМЕНТ ЗАМОВЛЕННЯ)
        q2 = """
        INSERT INTO luna_shop_order_items (order_id, product_id, name, price_kop, qty)
        VALUES (:oid, :pid, :n, :p, :q)
        """
        for it in items:
            await db_execute(q2, {
                "oid": order_id,
                "pid": int(it["product_id"]),
                "n": str(it["name"])[:128],
                "p": int(it["effective_price_kop"]),
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

    @staticmethod
    async def admin_list_last_orders(tenant_id: str, limit: int = 50) -> list[dict]:
        q = """
        SELECT id, user_id, status, total_kop, created_ts
        FROM luna_shop_orders
        WHERE tenant_id = :tid
        ORDER BY id DESC
        LIMIT :lim
        """
        return await db_fetch_all(q, {"tid": tenant_id, "lim": int(limit)})

    @staticmethod
    async def admin_get_order_items(order_id: int) -> list[dict]:
        q = """
        SELECT product_id, name, price_kop, qty
        FROM luna_shop_order_items
        WHERE order_id = :oid
        ORDER BY id ASC
        """
        return await db_fetch_all(q, {"oid": int(order_id)})