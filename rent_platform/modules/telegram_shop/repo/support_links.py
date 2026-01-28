# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from typing import Any

from rent_platform.db.session import db_execute, db_fetch_all, db_fetch_one


class TelegramShopSupportLinksRepo:
    """
    Таблиця: telegram_shop_support_links
    Очікувані колонки:
      - tenant_id (text)
      - key (text)
      - title (text, nullable)
      - url (text, nullable)
      - enabled (bool/int)
      - sort (int, nullable)
      - created_ts (int/bigint) NOT NULL  <-- у тебе є, бо БД ругається
      - updated_ts (int/bigint) NOT NULL  <-- дуже ймовірно теж є
    PK: (tenant_id, key)
    """

    @staticmethod
    async def get(tenant_id: str, key: str) -> dict[str, Any] | None:
        q = """
        SELECT tenant_id, key, COALESCE(title,'') AS title, COALESCE(url,'') AS url,
               COALESCE(enabled,false) AS enabled, COALESCE(sort,0) AS sort
        FROM telegram_shop_support_links
        WHERE tenant_id = :tid AND key = :key
        LIMIT 1
        """
        return await db_fetch_one(q, {"tid": tenant_id, "key": key})

    @staticmethod
    async def list_all(tenant_id: str) -> list[dict[str, Any]]:
        q = """
        SELECT tenant_id, key, COALESCE(title,'') AS title, COALESCE(url,'') AS url,
               COALESCE(enabled,false) AS enabled, COALESCE(sort,0) AS sort
        FROM telegram_shop_support_links
        WHERE tenant_id = :tid
        ORDER BY COALESCE(sort,0) ASC, key ASC
        """
        return await db_fetch_all(q, {"tid": tenant_id}) or []

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
        """
        Postgres upsert по (tenant_id, key).
        ФІКС: created_ts/updated_ts, бо в таблиці NOT NULL.
        """
        now = int(time.time())
        q = """
        INSERT INTO telegram_shop_support_links
            (tenant_id, key, title, url, enabled, sort, created_ts, updated_ts)
        VALUES
            (:tid, :key, COALESCE(:title,''), COALESCE(:url,''), COALESCE(:enabled,false), COALESCE(:sort,0), :now, :now)
        ON CONFLICT (tenant_id, key)
        DO UPDATE SET
            title = CASE WHEN :title IS NULL THEN telegram_shop_support_links.title ELSE COALESCE(:title,'') END,
            url   = CASE WHEN :url   IS NULL THEN telegram_shop_support_links.url   ELSE COALESCE(:url,'')   END,
            enabled = CASE WHEN :enabled IS NULL THEN telegram_shop_support_links.enabled ELSE COALESCE(:enabled,false) END,
            sort  = CASE WHEN :sort  IS NULL THEN telegram_shop_support_links.sort  ELSE COALESCE(:sort,0)  END,
            updated_ts = :now
        """
        await db_execute(
            q,
            {
                "tid": tenant_id,
                "key": key,
                "title": title,
                "url": url,
                "enabled": enabled,
                "sort": sort,
                "now": now,
            },
        )

    @staticmethod
    async def set_url(tenant_id: str, key: str, url: str) -> None:
        await TelegramShopSupportLinksRepo.upsert(tenant_id, key, url=(url or "").strip())

    @staticmethod
    async def set_enabled(tenant_id: str, key: str, enabled: bool) -> None:
        await TelegramShopSupportLinksRepo.upsert(tenant_id, key, enabled=bool(enabled))

    @staticmethod
    async def toggle_enabled(tenant_id: str, key: str) -> bool:
        cur = await TelegramShopSupportLinksRepo.get(tenant_id, key) or {}
        now = bool(cur.get("enabled"))
        newv = not now
        await TelegramShopSupportLinksRepo.set_enabled(tenant_id, key, newv)
        return newv

    @staticmethod
    async def ensure_defaults(tenant_id: str) -> None:
        """
        Створює дефолтні ключі (щоб меню було завжди з пунктами).
        """
        defaults: list[tuple[str, str, int]] = [
            ("support_chat", "Наш чат", 10),
            ("support_site", "Наш сайт", 20),
            ("support_manager", "Менеджер", 30),
            ("support_email", "Пошта", 40),
            ("announce_chat_id", "Автопост новинок: chat_id", 90),
        ]
        for k, t, s in defaults:
            await TelegramShopSupportLinksRepo.upsert(tenant_id, k, title=t, sort=s)