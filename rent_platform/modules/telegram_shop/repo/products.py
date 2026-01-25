from __future__ import annotations

from typing import Any

from rent_platform.db.session import db_fetch_all


class ProductsRepo:
    @staticmethod
    async def list_products(tenant_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """
        Мінімальний repo під каталог.
        Повертає: [{id, tenant_id, name, price_kop, is_active, created_ts}, ...]
        """
        q = """
        SELECT
            id,
            tenant_id,
            name,
            price_kop,
            is_active,
            created_ts
        FROM telegram_shop_products
        WHERE tenant_id = :tid AND is_active = true
        ORDER BY id DESC
        LIMIT :lim
        """
        rows = await db_fetch_all(q, {"tid": tenant_id, "lim": int(limit)}) or []
        return [dict(r) for r in rows]