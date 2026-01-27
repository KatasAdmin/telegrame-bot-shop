from __future__ import annotations

from typing import Any

from rent_platform.db.session import db_execute, db_fetch_all, db_fetch_one


class TelegramShopSupportLinksRepo:
    """
    Таблиця: telegram_shop_support_links
    key: channel | site | manager | chat | email ...
    url: будь-який url (mailto:, https://, tg://resolve?domain=...)
    enabled: 1/0
    sort: порядок
    """

    DEFAULTS: list[dict[str, Any]] = [
        {"key": "channel", "title": "📣 Наш канал", "url": "https://t.me/your_channel", "enabled": 1, "sort": 10},
        {"key": "site", "title": "🌐 Наш сайт", "url": "https://example.com", "enabled": 0, "sort": 20},
        {"key": "manager", "title": "👤 Менеджер", "url": "https://t.me/your_manager", "enabled": 1, "sort": 30},
        {"key": "chat", "title": "💬 Наш чат", "url": "https://t.me/your_chat", "enabled": 0, "sort": 40},
        {"key": "email", "title": "✉️ Пошта", "url": "mailto:support@example.com", "enabled": 0, "sort": 50},
        # канал для автопостів (НЕ показуємо юзерам, бо title без емодзі/кнопки можна вимкнути)
        {"key": "announce_chat_id", "title": "🔧 announce_chat_id", "url": "", "enabled": 0, "sort": 900},
    ]

    @staticmethod
    async def ensure_defaults(tenant_id: str) -> None:
        # таблиця може бути ще не створена міграцією — тоді цей репо впаде.
        # але у нормі ти додаси міграцію нижче.
        for it in TelegramShopSupportLinksRepo.DEFAULTS:
            await db_execute(
                """
                INSERT INTO telegram_shop_support_links (tenant_id, key, title, url, enabled, sort)
                VALUES (%(tenant_id)s, %(key)s, %(title)s, %(url)s, %(enabled)s, %(sort)s)
                ON CONFLICT (tenant_id, key) DO NOTHING
                """,
                {
                    "tenant_id": tenant_id,
                    "key": it["key"],
                    "title": it["title"],
                    "url": it["url"],
                    "enabled": int(it["enabled"]),
                    "sort": int(it["sort"]),
                },
            )

    @staticmethod
    async def list_enabled(tenant_id: str) -> list[dict[str, Any]]:
        return await db_fetch_all(
            """
            SELECT key, title, url, enabled, sort
            FROM telegram_shop_support_links
            WHERE tenant_id=%(tenant_id)s AND enabled=1
              AND key NOT IN ('announce_chat_id')
            ORDER BY sort ASC, key ASC
            """,
            {"tenant_id": tenant_id},
        )

    @staticmethod
    async def list_all(tenant_id: str) -> list[dict[str, Any]]:
        return await db_fetch_all(
            """
            SELECT key, title, url, enabled, sort
            FROM telegram_shop_support_links
            WHERE tenant_id=%(tenant_id)s
            ORDER BY sort ASC, key ASC
            """,
            {"tenant_id": tenant_id},
        )

    @staticmethod
    async def get(tenant_id: str, key: str) -> dict[str, Any] | None:
        return await db_fetch_one(
            """
            SELECT key, title, url, enabled, sort
            FROM telegram_shop_support_links
            WHERE tenant_id=%(tenant_id)s AND key=%(key)s
            """,
            {"tenant_id": tenant_id, "key": key},
        )

    @staticmethod
    async def toggle(tenant_id: str, key: str) -> None:
        await db_execute(
            """
            UPDATE telegram_shop_support_links
            SET enabled = CASE WHEN enabled=1 THEN 0 ELSE 1 END
            WHERE tenant_id=%(tenant_id)s AND key=%(key)s
            """,
            {"tenant_id": tenant_id, "key": key},
        )

    @staticmethod
    async def set_url(tenant_id: str, key: str, url: str) -> None:
        await db_execute(
            """
            UPDATE telegram_shop_support_links
            SET url=%(url)s
            WHERE tenant_id=%(tenant_id)s AND key=%(key)s
            """,
            {"tenant_id": tenant_id, "key": key, "url": url},
        )