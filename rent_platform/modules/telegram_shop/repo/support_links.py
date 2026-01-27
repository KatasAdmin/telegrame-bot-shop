from __future__ import annotations

import time
from typing import Any

from rent_platform.db.session import db_fetch_all, db_fetch_one, db_execute


class TelegramShopSupportLinksRepo:
    """
    Табличка конфігів для "Підтримка" + для announce_chat_id.
    key — унікальний в рамках tenant.
    """

    DEFAULTS: list[dict[str, Any]] = [
        {"key": "support_channel", "title": "Наш канал", "url": "", "enabled": False, "sort": 10},
        {"key": "support_site", "title": "Наш сайт", "url": "", "enabled": False, "sort": 20},
        {"key": "support_manager", "title": "Менеджер", "url": "", "enabled": False, "sort": 30},
        {"key": "support_chat", "title": "Наш чат", "url": "", "enabled": False, "sort": 40},
        {"key": "support_email", "title": "Пошта", "url": "", "enabled": False, "sort": 50},
        # автопост нових товарів (url тут = chat_id каналу, наприклад -1001234567890)
        {"key": "announce_chat_id", "title": "Автопост новинок: chat_id", "url": "", "enabled": False, "sort": 1000},
    ]

    @staticmethod
    async def ensure_defaults(tenant_id: str) -> None:
        now = int(time.time())
        for d in TelegramShopSupportLinksRepo.DEFAULTS:
            q = """
            INSERT INTO telegram_shop_support_links
                (tenant_id, key, title, url, enabled, sort, created_ts, updated_ts)
            VALUES
                (:tid, :k, :t, :u, :e, :s, :ts, :ts)
            ON CONFLICT (tenant_id, key) DO NOTHING
            """
            await db_execute(
                q,
                {
                    "tid": str(tenant_id),
                    "k": str(d["key"]),
                    "t": str(d["title"]),
                    "u": str(d.get("url") or ""),
                    "e": bool(d.get("enabled") or False),
                    "s": int(d.get("sort") or 100),
                    "ts": now,
                },
            )

    @staticmethod
    async def list_all(tenant_id: str) -> list[dict[str, Any]]:
        q = """
        SELECT id, tenant_id, key, title, url, enabled, sort, created_ts, updated_ts
        FROM telegram_shop_support_links
        WHERE tenant_id = :tid
        ORDER BY sort ASC, id ASC
        """
        return await db_fetch_all(q, {"tid": str(tenant_id)}) or []

    @staticmethod
    async def list_enabled(tenant_id: str) -> list[dict[str, Any]]:
        q = """
        SELECT id, tenant_id, key, title, url, enabled, sort, created_ts, updated_ts
        FROM telegram_shop_support_links
        WHERE tenant_id = :tid AND enabled = true
        ORDER BY sort ASC, id ASC
        """
        return await db_fetch_all(q, {"tid": str(tenant_id)}) or []

    @staticmethod
    async def get(tenant_id: str, key: str) -> dict[str, Any] | None:
        q = """
        SELECT id, tenant_id, key, title, url, enabled, sort, created_ts, updated_ts
        FROM telegram_shop_support_links
        WHERE tenant_id = :tid AND key = :k
        LIMIT 1
        """
        row = await db_fetch_one(q, {"tid": str(tenant_id), "k": str(key)})
        return row if row else None

    @staticmethod
    async def upsert(
        tenant_id: str,
        key: str,
        *,
        title: str | None = None,
        url: str | None = None,
        enabled: bool | None = None,
        sort: int | None = None,
    ) -> None:
        now = int(time.time())
        # якщо не існує — створимо
        q_ins = """
        INSERT INTO telegram_shop_support_links
            (tenant_id, key, title, url, enabled, sort, created_ts, updated_ts)
        VALUES
            (:tid, :k, :t, :u, :e, :s, :ts, :ts)
        ON CONFLICT (tenant_id, key)
        DO UPDATE SET
            title = COALESCE(:t2, telegram_shop_support_links.title),
            url = COALESCE(:u2, telegram_shop_support_links.url),
            enabled = COALESCE(:e2, telegram_shop_support_links.enabled),
            sort = COALESCE(:s2, telegram_shop_support_links.sort),
            updated_ts = :ts2
        """
        await db_execute(
            q_ins,
            {
                "tid": str(tenant_id),
                "k": str(key),
                "t": (title or "") if title is not None else "",
                "u": (url or "") if url is not None else "",
                "e": bool(enabled) if enabled is not None else False,
                "s": int(sort) if sort is not None else 100,
                "ts": now,
                # update поля (якщо None — не чіпаємо)
                "t2": (title or "").strip() if title is not None else None,
                "u2": (url or "").strip() if url is not None else None,
                "e2": bool(enabled) if enabled is not None else None,
                "s2": int(sort) if sort is not None else None,
                "ts2": now,
            },
        )

    @staticmethod
    async def set_enabled(tenant_id: str, key: str, enabled: bool) -> None:
        q = """
        UPDATE telegram_shop_support_links
        SET enabled = :e, updated_ts = :ts
        WHERE tenant_id = :tid AND key = :k
        """
        await db_execute(q, {"tid": str(tenant_id), "k": str(key), "e": bool(enabled), "ts": int(time.time())})

    @staticmethod
    async def delete(tenant_id: str, key: str) -> None:
        q = """
        DELETE FROM telegram_shop_support_links
        WHERE tenant_id = :tid AND key = :k
        """
        await db_execute(q, {"tid": str(tenant_id), "k": str(key)})