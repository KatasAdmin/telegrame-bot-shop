# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import time
from typing import Any

from rent_platform.db.session import db_fetch_all, db_fetch_one, db_execute


class TelegramShopPaymentProvidersRepo:
    """
    Табличка: telegram_shop_payment_providers
    (по факту: універсальні settings інтеграцій)

    Правила:
      - enabled = true -> можна показувати/використовувати
      - value == "" або "-" / "—" / "0" -> вважаємо як "нема", авто-вимикаємо
      - ключі з префіксами:
          pay_*  -> оплата
          np_*   -> нова пошта
          fop_*  -> реквізити/дані ФОП
          shop_* -> інше
    """

    # ====== БАЗОВІ СЛОТИ (можеш додавати/міняти як хочеш) ======
    DEFAULTS: list[dict[str, Any]] = [
        # ---------------- PAYMENT ----------------
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
            "title": "Ручна оплата (реквізити/інструкція)",
            "enabled": False,
            "hint": "Встав реквізити/IBAN/карту/текст інструкції. Якщо `-` → сховається.",
        },

        # ---------------- NOVA POSHTA ----------------
        {
            "key": "np_api_key",
            "title": "Нова Пошта: API key",
            "enabled": False,
            "hint": "Встав API key. Якщо `-` → вимкнеться.",
        },
        {
            "key": "np_sender_phone",
            "title": "Нова Пошта: телефон відправника",
            "enabled": False,
            "hint": "Напр: +380XXXXXXXXX. Якщо `-` → вимкнеться.",
        },
        {
            "key": "np_sender_city_ref",
            "title": "Нова Пошта: CityRef відправника",
            "enabled": False,
            "hint": "CityRef (з NP API). Можна зберігати і як JSON. Якщо `-` → вимкнеться.",
        },
        {
            "key": "np_sender_warehouse_ref",
            "title": "Нова Пошта: WarehouseRef відправника",
            "enabled": False,
            "hint": "WarehouseRef (з NP API). Якщо `-` → вимкнеться.",
        },

        # ---------------- FOP / REQUISITES ----------------
        {
            "key": "fop_name",
            "title": "ФОП: ПІБ / Назва",
            "enabled": False,
            "hint": "Напр: ФОП Іванов Іван. Якщо `-` → вимкнеться.",
        },
        {
            "key": "fop_ipn",
            "title": "ФОП: ІПН",
            "enabled": False,
            "hint": "10 цифр. Якщо `-` → вимкнеться.",
        },
        {
            "key": "fop_iban",
            "title": "ФОП: IBAN",
            "enabled": False,
            "hint": "UAxxxxxxxxxxxxxxxxxxxxxx. Якщо `-` → вимкнеться.",
        },
        {
            "key": "fop_address",
            "title": "ФОП: Адреса",
            "enabled": False,
            "hint": "Адреса для документів/чеків. Якщо `-` → вимкнеться.",
        },

        # ---------------- OTHER ----------------
        {
            "key": "shop_support_phone",
            "title": "Магазин: телефон підтримки",
            "enabled": False,
            "hint": "Напр: +380XXXXXXXXX. Якщо `-` → вимкнеться.",
        },
        {
            "key": "shop_sender_note",
            "title": "Магазин: примітка (текст)",
            "enabled": False,
            "hint": "Будь-який текст, який треба показувати клієнту/в замовленні. Якщо `-` → вимкнеться.",
        },
    ]

    # ---------------- helpers ----------------
    @staticmethod
    def _norm_value(value: str) -> str:
        v = (value or "").strip()
        if v in ("-", "—", "0"):
            return ""
        return v

    @staticmethod
    async def ensure_defaults(tenant_id: str) -> None:
        ts = int(time.time())
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
                    "title": d.get("title") or d["key"],
                    "enabled": bool(d.get("enabled", False)),
                    "value": "",
                    "ts": ts,
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
    async def list_by_prefix(tenant_id: str, prefix: str) -> list[dict[str, Any]]:
        p = (prefix or "").strip()
        q = """
        SELECT key, title, enabled, COALESCE(value,'') AS value
        FROM telegram_shop_payment_providers
        WHERE tenant_id = :tid AND key LIKE :pref
        ORDER BY key ASC
        """
        return await db_fetch_all(q, {"tid": tenant_id, "pref": f"{p}%"}) or []

    @staticmethod
    async def list_enabled_by_prefix(tenant_id: str, prefix: str) -> list[dict[str, Any]]:
        p = (prefix or "").strip()
        q = """
        SELECT key, title, enabled, COALESCE(value,'') AS value
        FROM telegram_shop_payment_providers
        WHERE tenant_id = :tid
          AND key LIKE :pref
          AND enabled = true
          AND COALESCE(value,'') <> ''
        ORDER BY key ASC
        """
        return await db_fetch_all(q, {"tid": tenant_id, "pref": f"{p}%"}) or []

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
    async def get_value(tenant_id: str, key: str, default: str = "") -> str:
        it = await TelegramShopPaymentProvidersRepo.get(tenant_id, key) or {}
        v = str(it.get("value") or "").strip()
        return v if v else default

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
        v = TelegramShopPaymentProvidersRepo._norm_value(value)

        q = """
        UPDATE telegram_shop_payment_providers
        SET value = :v,
            enabled = CASE WHEN :v = '' THEN false ELSE enabled END,
            updated_ts = :ts
        WHERE tenant_id = :tid AND key = :key
        """
        await db_execute(q, {"tid": tenant_id, "key": key, "v": v, "ts": int(time.time())})

    @staticmethod
    async def set_json(tenant_id: str, key: str, payload: dict[str, Any]) -> None:
        """
        Зручний спосіб зберігати складні штуки (наприклад NP refs) як JSON рядок.
        """
        v = json.dumps(payload or {}, ensure_ascii=False)
        await TelegramShopPaymentProvidersRepo.set_value(tenant_id, key, v)

    @staticmethod
    async def get_json(tenant_id: str, key: str) -> dict[str, Any]:
        raw = await TelegramShopPaymentProvidersRepo.get_value(tenant_id, key, default="")
        if not raw:
            return {}
        try:
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}

    @staticmethod
    async def enable_if_has_value(tenant_id: str, key: str) -> None:
        it = await TelegramShopPaymentProvidersRepo.get(tenant_id, key) or {}
        v = str(it.get("value") or "").strip()
        if v:
            await TelegramShopPaymentProvidersRepo.set_enabled(tenant_id, key, True)