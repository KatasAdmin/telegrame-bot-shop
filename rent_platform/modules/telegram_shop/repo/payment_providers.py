# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from typing import Any

from rent_platform.db.session import db_fetch_all, db_fetch_one, db_execute


class TelegramShopPaymentProvidersRepo:
    """
    Табличка: telegram_shop_payment_providers
    Логіка:
      - enabled = true -> кнопка доступна юзеру
      - value == "-" або "" -> вважаємо як "нема", авт вимикаємо
    """

    DEFAULTS: list[dict[str, Any]] = [
        {
            "key": "pay_privat",
            "title": "Privat (merchant/key)",
            "enabled": False,
            "hint": "Встав ключ/мерчант/дані. Якщо `-` → сховається.",
        },
        {
            "key": "pay_mono",
            "title": "Mono (token/merchant)",
            "enabled": False,
            "hint": "Встав token/мерчант/дані. Якщо `-` → сховається.",
        },
        {
            "key": "pay_crypto_bot",
            "title": "Crypto Bot (token)",
            "enabled": False,
            "hint": "Встав token CryptoBot. Якщо `-` → сховається.",
        },
        {
            "key": "pay_manual",
            "title": "Ручна оплата (реквізити)",
            "enabled": False,
            "hint": "Встав реквізити/IBAN/карту/текст інструкції. Якщо `-` → сховається.",
        },
    ]

    @staticmethod
    async def ensure_defaults(tenant_id: str) -> None:
        for d in TelegramShopPaymentProvidersRepo.DEFAULTS:
            q = """
            INSERT INTO telegram_shop_payment_providers (tenant_id, key, title, enabled, value, created_ts, updated_ts)
            VALUES (:tid, :key, :title, :enabled, :value, :ts, :ts)
            ON CONFLICT (tenant_id, key) DO NOTHING
            """
            await db_execute(
                q,
                {
                    "tid": tenant_id,
                    "key": d["key"],
                    "title": d["title"],
                    "enabled": bool(d.get("enabled", False)),
                    "value": "",
                    "ts": int(time.time()),
                },
            )

    @staticmethod
    async def list_all(tenant_id: str) -> list[dict[str, Any]]:
        q = """
        SELECT key, title, enabled, COALESCE(value,'') AS value
        FROM telegram_shop_payment_providers
        WHERE tenant_id = :tid
        ORDER BY key ASC
        """
        return await db_fetch_all(q, {"tid": tenant_id}) or []

    @staticmethod
    async def get(tenant_id: str, key: str) -> dict[str, Any] | None:
        q = """
        SELECT key, title, enabled, COALESCE(value,'') AS value
        FROM telegram_shop_payment_providers
        WHERE tenant_id = :tid AND key = :key
        LIMIT 1
        """
        return await db_fetch_one(q, {"tid": tenant_id, "key": key})

    @staticmethod
    async def set_enabled(tenant_id: str, key: str, enabled: bool) -> None:
        q = """
        UPDATE telegram_shop_payment_providers
        SET enabled = :en, updated_ts = :ts
        WHERE tenant_id = :tid AND key = :key
        """
        await db_execute(q, {"tid": tenant_id, "key": key, "en": bool(enabled), "ts": int(time.time())})

    @staticmethod
    async def toggle_enabled(tenant_id: str, key: str) -> None:
        it = await TelegramShopPaymentProvidersRepo.get(tenant_id, key) or {}
        cur = bool(it.get("enabled"))
        await TelegramShopPaymentProvidersRepo.set_enabled(tenant_id, key, not cur)

    @staticmethod
    async def set_value(tenant_id: str, key: str, value: str) -> None:
        """
        value == "-" або "" -> очищаємо і вимикаємо
        """
        v = (value or "").strip()
        if v in ("-", "—", "0"):
            v = ""

        q = """
        UPDATE telegram_shop_payment_providers
        SET value = :v, enabled = CASE WHEN :v = '' THEN false ELSE enabled END, updated_ts = :ts
        WHERE tenant_id = :tid AND key = :key
        """
        await db_execute(q, {"tid": tenant_id, "key": key, "v": v, "ts": int(time.time())})

    @staticmethod
    async def enable_if_has_value(tenant_id: str, key: str) -> None:
        it = await TelegramShopPaymentProvidersRepo.get(tenant_id, key) or {}
        v = str(it.get("value") or "").strip()
        if v:
            await TelegramShopPaymentProvidersRepo.set_enabled(tenant_id, key, True)