from __future__ import annotations

import time
from typing import Any

from rent_platform.db.session import db_fetch_one, db_fetch_all, db_execute


class CategoriesRepo:
    # системні імена
    DEFAULT_NAME = "Без категорії"
    SHOW_ALL_FLAG_NAME = "__SHOW_ALL_BUTTON__"

    # sort < 0 = прихована для покупця
    DEFAULT_HIDDEN_SORT = -100
    FLAG_HIDDEN_SORT = -999

    @staticmethod
    async def ensure_default(tenant_id: str) -> int:
        """
        Гарантує категорію "Без категорії".
        ВАЖЛИВО: за замовчуванням вона прихована для покупця (sort = -100).
        """
        q_ins = """
        INSERT INTO telegram_shop_categories (tenant_id, name, sort, created_ts)
        VALUES (:tid, :name, :s, :ts)
        ON CONFLICT (tenant_id, name) DO NOTHING
        RETURNING id
        """
        row = await db_fetch_one(
            q_ins,
            {"tid": tenant_id, "name": CategoriesRepo.DEFAULT_NAME, "s": int(CategoriesRepo.DEFAULT_HIDDEN_SORT), "ts": int(time.time())},
        )
        if row and row.get("id") is not None:
            return int(row["id"])

        q_get = """
        SELECT id
        FROM telegram_shop_categories
        WHERE tenant_id = :tid AND name = :name
        LIMIT 1
        """
        row2 = await db_fetch_one(q_get, {"tid": tenant_id, "name": CategoriesRepo.DEFAULT_NAME})
        return int(row2["id"])

    @staticmethod
    async def get_default(tenant_id: str) -> dict[str, Any] | None:
        q = """
        SELECT id, tenant_id, name, sort, created_ts
        FROM telegram_shop_categories
        WHERE tenant_id = :tid AND name = :name
        LIMIT 1
        """
        return await db_fetch_one(q, {"tid": tenant_id, "name": CategoriesRepo.DEFAULT_NAME})

    @staticmethod
    async def set_default_visible(tenant_id: str, visible: bool) -> None:
        await CategoriesRepo.ensure_default(tenant_id)
        new_sort = 0 if visible else CategoriesRepo.DEFAULT_HIDDEN_SORT
        q = """
        UPDATE telegram_shop_categories
        SET sort = :s
        WHERE tenant_id = :tid AND name = :name
        """
        await db_execute(q, {"tid": tenant_id, "name": CategoriesRepo.DEFAULT_NAME, "s": int(new_sort)})

    @staticmethod
    async def is_default_visible(tenant_id: str) -> bool:
        row = await CategoriesRepo.get_default(tenant_id)
        if not row:
            return False
        return int(row.get("sort") or 0) >= 0

    # --------- show_all flag (не категорія, а налаштування) ---------

    @staticmethod
    async def ensure_show_all_flag(tenant_id: str) -> None:
        q = """
        INSERT INTO telegram_shop_categories (tenant_id, name, sort, created_ts)
        VALUES (:tid, :name, :s, :ts)
        ON CONFLICT (tenant_id, name) DO NOTHING
        """
        await db_execute(q, {"tid": tenant_id, "name": CategoriesRepo.SHOW_ALL_FLAG_NAME, "s": int(CategoriesRepo.FLAG_HIDDEN_SORT), "ts": int(time.time())})

    @staticmethod
    async def set_show_all_enabled(tenant_id: str, enabled: bool) -> None:
        await CategoriesRepo.ensure_show_all_flag(tenant_id)
        # enabled=True => sort = 0, enabled=False => sort = -999
        s = 0 if enabled else CategoriesRepo.FLAG_HIDDEN_SORT
        q = """
        UPDATE telegram_shop_categories
        SET sort = :s
        WHERE tenant_id = :tid AND name = :name
        """
        await db_execute(q, {"tid": tenant_id, "name": CategoriesRepo.SHOW_ALL_FLAG_NAME, "s": int(s)})

    @staticmethod
    async def is_show_all_enabled(tenant_id: str) -> bool:
        await CategoriesRepo.ensure_show_all_flag(tenant_id)
        q = """
        SELECT sort
        FROM telegram_shop_categories
        WHERE tenant_id = :tid AND name = :name
        LIMIT 1
        """
        row = await db_fetch_one(q, {"tid": tenant_id, "name": CategoriesRepo.SHOW_ALL_FLAG_NAME})
        return bool(row) and int(row.get("sort") or 0) >= 0

    # --------- lists ---------

    @staticmethod
    async def list_public(tenant_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """
        Для покупця: тільки видимі категорії (sort >= 0)
        + прибираємо системні (__...__)
        """
        q = """
        SELECT id, tenant_id, name, sort, created_ts
        FROM telegram_shop_categories
        WHERE tenant_id = :tid
          AND sort >= 0
          AND name NOT LIKE '\\_\\_%' ESCAPE '\\'
        ORDER BY sort ASC, id ASC
        LIMIT :lim
        """
        return await db_fetch_all(q, {"tid": tenant_id, "lim": int(limit)}) or []

    @staticmethod
    async def list(tenant_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """
        Для адміна: всі категорії, крім системних (__...__) можна показувати теж (але ми їх зазвичай не показуємо в пікерах).
        """
        q = """
        SELECT id, tenant_id, name, sort, created_ts
        FROM telegram_shop_categories
        WHERE tenant_id = :tid
        ORDER BY sort ASC, id ASC
        LIMIT :lim
        """
        return await db_fetch_all(q, {"tid": tenant_id, "lim": int(limit)}) or []

    @staticmethod
    async def create(tenant_id: str, name: str, sort: int = 100) -> int:
        nm = (name or "").strip()[:64]
        if not nm:
            raise ValueError("empty category name")

        q_ins = """
        INSERT INTO telegram_shop_categories (tenant_id, name, sort, created_ts)
        VALUES (:tid, :name, :sort, :ts)
        ON CONFLICT (tenant_id, name) DO NOTHING
        RETURNING id
        """
        row = await db_fetch_one(q_ins, {"tid": tenant_id, "name": nm, "sort": int(sort), "ts": int(time.time())})
        if row and row.get("id") is not None:
            return int(row["id"])

        q_get = """
        SELECT id
        FROM telegram_shop_categories
        WHERE tenant_id = :tid AND name = :name
        LIMIT 1
        """
        row2 = await db_fetch_one(q_get, {"tid": tenant_id, "name": nm})
        return int(row2["id"])

    @staticmethod
    async def delete(tenant_id: str, category_id: int) -> None:
        """
        Видалення категорії:
        - дефолтну ("Без категорії") видаляти не можна
        - товари з цієї категорії переносимо в дефолтну
        """
        category_id = int(category_id)
        default_id = int(await CategoriesRepo.ensure_default(tenant_id))

        if category_id == default_id:
            raise ValueError("cannot delete default category")

        # переносимо товари в дефолтну
        q_move = """
        UPDATE telegram_shop_products
        SET category_id = :to_cid
        WHERE tenant_id = :tid AND category_id = :from_cid
        """
        await db_execute(q_move, {"tid": tenant_id, "from_cid": category_id, "to_cid": default_id})

        # видаляємо категорію
        q_del = """
        DELETE FROM telegram_shop_categories
        WHERE tenant_id = :tid AND id = :cid
        """
        await db_execute(q_del, {"tid": tenant_id, "cid": category_id})