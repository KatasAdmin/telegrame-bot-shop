# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from typing import Any

from rent_platform.db.session import db_fetch_all, db_fetch_one, db_execute


def _now() -> int:
    return int(time.time())


DEFAULTS: list[dict[str, Any]] = [
    # WayForPay
    {"key": "w4p_merchant_account", "title": "WayForPay: merchantAccount", "value": "", "enabled": False, "is_secret": False},
    {"key": "w4p_secret_key", "title": "WayForPay: secretKey", "value": "", "enabled": False, "is_secret": True},
    {"key": "w4p_domain", "title": "WayForPay: merchantDomainName", "value": "", "enabled": False, "is_secret": False},

    # Security
    {"key": "w4p_allow_ips", "title": "WayForPay: IP allowlist (comma)", "value": "", "enabled": False, "is_secret": False},

    # Nova Poshta placeholder
    {"key": "novaposhta_api_key", "title": "Нова Пошта: API key", "value": "", "enabled": False, "is_secret": True},
]


class TelegramShopIntegrationsRepo:
    @staticmethod
    async def ensure_defaults(tenant_id: str) -> None:
        for d in DEFAULTS:
            q = """
            INSERT INTO telegram_shop_integrations (tenant_id, key, title, value, enabled, is_secret, updated_ts)
            VALUES (:tid, :key, :title, :value, :enabled, :is_secret, :ts)
            ON CONFLICT (tenant_id, key) DO NOTHING
            """
            await db_execute(
                q,
                {
                    "tid": tenant_id,
                    "key": d["key"],
                    "title": d["title"],
                    "value": d["value"],
                    "enabled": bool(d["enabled"]),
                    "is_secret": bool(d["is_secret"]),
                    "ts": _now(),
                },
            )

    @staticmethod
    async def list_all(tenant_id: str) -> list[dict[str, Any]]:
        q = """
        SELECT key, title, value, enabled, is_secret, updated_ts
        FROM telegram_shop_integrations
        WHERE tenant_id = :tid
        ORDER BY key ASC
        """
        return await db_fetch_all(q, {"tid": tenant_id}) or []

    @staticmethod
    async def get(tenant_id: str, key: str) -> dict[str, Any] | None:
        q = """
        SELECT key, title, value, enabled, is_secret, updated_ts
        FROM telegram_shop_integrations
        WHERE tenant_id = :tid AND key = :key
        LIMIT 1
        """
        return await db_fetch_one(q, {"tid": tenant_id, "key": key})

    @staticmethod
    async def set_value(tenant_id: str, key: str, value: str) -> None:
        q = """
        UPDATE telegram_shop_integrations
        SET value = :v, updated_ts = :ts
        WHERE tenant_id = :tid AND key = :key
        """
        await db_execute(q, {"tid": tenant_id, "key": key, "v": str(value or ""), "ts": _now()})

    @staticmethod
    async def set_enabled(tenant_id: str, key: str, enabled: bool) -> None:
        q = """
        UPDATE telegram_shop_integrations
        SET enabled = :en, updated_ts = :ts
        WHERE tenant_id = :tid AND key = :key
        """
        await db_execute(q, {"tid": tenant_id, "key": key, "en": bool(enabled), "ts": _now()})

    @staticmethod
    async def toggle_enabled(tenant_id: str, key: str) -> None:
        cur = await TelegramShopIntegrationsRepo.get(tenant_id, key) or {}
        await TelegramShopIntegrationsRepo.set_enabled(tenant_id, key, not bool(cur.get("enabled")))

    @staticmethod
    async def get_value(tenant_id: str, key: str) -> str:
        row = await TelegramShopIntegrationsRepo.get(tenant_id, key) or {}
        return str(row.get("value") or "")

    @staticmethod
    async def is_enabled(tenant_id: str, key: str) -> bool:
        row = await TelegramShopIntegrationsRepo.get(tenant_id, key) or {}
        return bool(row.get("enabled"))