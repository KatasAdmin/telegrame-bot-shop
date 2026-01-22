from __future__ import annotations

import json
import secrets
import time
from typing import Any

from rent_platform.db.session import db_fetch_one, db_fetch_all, db_execute


class TenantRepo:
    @staticmethod
    async def get_by_id(tenant_id: str) -> dict | None:
        q = """
        SELECT
            id,
            owner_user_id,
            bot_token,
            secret,
            status,
            created_ts,
            plan_key,
            paid_until_ts,
            paused_reason,
            display_name,
            product_key,
            warned_24h_ts,
            warned_3h_ts
        FROM tenants
        WHERE id = :id
        """
        return await db_fetch_one(q, {"id": tenant_id})


    @staticmethod
    async def list_active_for_billing() -> list[dict[str, Any]]:
        q = """
        SELECT
            id,
            owner_user_id,
            status,
            paused_reason,
            product_key,
            rate_per_min_kop,
            last_billed_ts,
            warned_24h_ts,
            warned_3h_ts
        FROM tenants
        WHERE status = 'active'
          AND product_key IS NOT NULL
        ORDER BY created_ts ASC
        """
        return await db_fetch_all(q, {})

    @staticmethod
    async def set_rate_and_last_billed(owner_user_id: int, tenant_id: str, rate_per_min_kop: int, last_billed_ts: int) -> bool:
        q = """
        UPDATE tenants
        SET rate_per_min_kop = :r,
            last_billed_ts = :lb
        WHERE id = :id AND owner_user_id = :uid
        """
        res = await db_execute(q, {"r": int(rate_per_min_kop), "lb": int(last_billed_ts), "id": tenant_id, "uid": int(owner_user_id)})
        if res is None:
            row = await TenantRepo.get_token_secret_for_owner(owner_user_id, tenant_id)
            return bool(row)
        try:
            return int(res) > 0
        except Exception:
            return True

    @staticmethod
    async def system_pause_billing(tenant_id: str) -> None:
        q = """
        UPDATE tenants
        SET status = 'paused',
            paused_reason = 'billing'
        WHERE id = :id
        """
        await db_execute(q, {"id": tenant_id})

    @staticmethod
    async def system_resume_if_billing(tenant_id: str) -> None:
        q = """
        UPDATE tenants
        SET status = 'active',
            paused_reason = NULL
        WHERE id = :id AND status='paused' AND paused_reason='billing'
        """
        await db_execute(q, {"id": tenant_id})


    @staticmethod
    async def list_by_owner(owner_user_id: int) -> list[dict[str, Any]]:
        q = """
        SELECT
            id,
            bot_token,
            secret,
            status,
            created_ts,
            plan_key,
            paid_until_ts,
            paused_reason,
            display_name,
            product_key,
            warned_24h_ts,
            warned_3h_ts
        FROM tenants
        WHERE owner_user_id = :uid
        ORDER BY created_ts DESC
        """
        rows = await db_fetch_all(q, {"uid": owner_user_id})
        return [
            {
                "id": r["id"],
                "name": r.get("display_name") or "Bot",
                "token": r["bot_token"],   # ⚠️ у UI не показуємо
                "secret": r["secret"],     # ⚠️ у UI не показуємо
                "status": r["status"],
                "plan_key": r.get("plan_key") or "free",
                "paid_until_ts": int(r.get("paid_until_ts") or 0),
                "paused_reason": r.get("paused_reason"),
                "product_key": r.get("product_key"),
                "warned_24h_ts": int(r.get("warned_24h_ts") or 0),
                "warned_3h_ts": int(r.get("warned_3h_ts") or 0),
            }
            for r in rows
        ]

    @staticmethod
    async def create(owner_user_id: int, bot_token: str) -> dict[str, Any]:
        tenant_id = secrets.token_hex(4)
        secret = secrets.token_urlsafe(24)
        created_ts = int(time.time())

        q = """
        INSERT INTO tenants (
            id, owner_user_id, bot_token, secret,
            status, created_ts,
            plan_key, paid_until_ts,
            paused_reason,
            display_name,
            product_key,
            warned_24h_ts, warned_3h_ts
        )
        VALUES (
            :id, :uid, :token, :secret,
            'active', :ts,
            'free', 0,
            NULL,
            'Bot',
            NULL,
            0, 0
        )
        """
        await db_execute(
            q,
            {"id": tenant_id, "uid": owner_user_id, "token": bot_token, "secret": secret, "ts": created_ts},
        )

        return {
            "id": tenant_id,
            "owner_user_id": owner_user_id,
            "bot_token": bot_token,
            "secret": secret,
            "status": "active",
            "plan_key": "free",
            "paid_until_ts": 0,
            "paused_reason": None,
            "display_name": "Bot",
            "product_key": None,
            "warned_24h_ts": 0,
            "warned_3h_ts": 0,
        }

    @staticmethod
    async def get_token_secret_for_owner(owner_user_id: int, tenant_id: str) -> dict | None:
        q = """
        SELECT
            id,
            bot_token,
            secret,
            status,
            plan_key,
            paid_until_ts,
            paused_reason,
            display_name,
            product_key,
            warned_24h_ts,
            warned_3h_ts
        FROM tenants
        WHERE id = :id AND owner_user_id = :uid
        """
        return await db_fetch_one(q, {"id": tenant_id, "uid": owner_user_id})

    @staticmethod
    async def set_status(owner_user_id: int, tenant_id: str, status: str, paused_reason: str | None = None) -> bool:
        q = """
        UPDATE tenants
        SET status = :st, paused_reason = :pr
        WHERE id = :id AND owner_user_id = :uid
        """
        res = await db_execute(q, {"st": status, "pr": paused_reason, "id": tenant_id, "uid": owner_user_id})
        if res is None:
            exists = await TenantRepo.get_token_secret_for_owner(owner_user_id, tenant_id)
            return bool(exists)
        try:
            return int(res) > 0
        except Exception:
            return True

    @staticmethod
    async def soft_delete(owner_user_id: int, tenant_id: str) -> bool:
        return await TenantRepo.set_status(owner_user_id, tenant_id, "deleted", paused_reason="manual")

    @staticmethod
    async def rotate_secret(owner_user_id: int, tenant_id: str) -> str | None:
        new_secret = secrets.token_urlsafe(24)
        q = """
        UPDATE tenants
        SET secret = :sec
        WHERE id = :id AND owner_user_id = :uid
        """
        res = await db_execute(q, {"sec": new_secret, "id": tenant_id, "uid": owner_user_id})
        if res is None:
            row = await TenantRepo.get_token_secret_for_owner(owner_user_id, tenant_id)
            return new_secret if row else None
        return new_secret

    @staticmethod
    async def set_paid_until(owner_user_id: int, tenant_id: str, paid_until_ts: int, plan_key: str = "basic") -> bool:
        q = """
        UPDATE tenants
        SET paid_until_ts = :p, plan_key = :plan
        WHERE id = :id AND owner_user_id = :uid
        """
        res = await db_execute(q, {"p": int(paid_until_ts), "plan": plan_key, "id": tenant_id, "uid": owner_user_id})
        if res is None:
            row = await TenantRepo.get_token_secret_for_owner(owner_user_id, tenant_id)
            return bool(row)
        try:
            return int(res) > 0
        except Exception:
            return True

    @staticmethod
    async def set_display_name(owner_user_id: int, tenant_id: str, display_name: str) -> bool:
        q = """
        UPDATE tenants
        SET display_name = :dn
        WHERE id = :id AND owner_user_id = :uid
        """
        res = await db_execute(
            q,
            {"dn": (display_name or "Bot").strip()[:128], "id": tenant_id, "uid": owner_user_id},
        )
        if res is None:
            row = await TenantRepo.get_token_secret_for_owner(owner_user_id, tenant_id)
            return bool(row)
        try:
            return int(res) > 0
        except Exception:
            return True

    @staticmethod
    async def set_product_key(owner_user_id: int, tenant_id: str, product_key: str | None) -> bool:
        q = """
        UPDATE tenants
        SET product_key = :pk
        WHERE id = :id AND owner_user_id = :uid
        """
        res = await db_execute(q, {"pk": product_key, "id": tenant_id, "uid": owner_user_id})
        if res is None:
            row = await TenantRepo.get_token_secret_for_owner(owner_user_id, tenant_id)
            return bool(row)
        try:
            return int(res) > 0
        except Exception:
            return True

    @staticmethod
    async def set_warned(owner_user_id: int, tenant_id: str, kind: str, ts: int) -> bool:
        col = "warned_24h_ts" if kind == "24h" else "warned_3h_ts"
        q = f"""
        UPDATE tenants
        SET {col} = :ts
        WHERE id = :id AND owner_user_id = :uid
        """
        res = await db_execute(q, {"ts": int(ts), "id": tenant_id, "uid": owner_user_id})
        if res is None:
            row = await TenantRepo.get_token_secret_for_owner(owner_user_id, tenant_id)
            return bool(row)
        try:
            return int(res) > 0
        except Exception:
            return True

    @staticmethod
    async def trial_used(owner_user_id: int, product_key: str) -> bool:
        q = """
        SELECT 1
        FROM tenant_trial_usage
        WHERE owner_user_id = :uid AND product_key = :pk
        """
        row = await db_fetch_one(q, {"uid": owner_user_id, "pk": product_key})
        return bool(row)

    @staticmethod
    async def mark_trial_used(owner_user_id: int, product_key: str, first_used_ts: int) -> None:
        q = """
        INSERT INTO tenant_trial_usage (owner_user_id, product_key, first_used_ts)
        VALUES (:uid, :pk, :ts)
        ON CONFLICT (owner_user_id, product_key)
        DO NOTHING
        """
        await db_execute(q, {"uid": owner_user_id, "pk": product_key, "ts": int(first_used_ts)})


    @staticmethod
    async def system_resume_all_billing_for_owner(owner_user_id: int) -> int:
        q = """
        UPDATE tenants
        SET status='active', paused_reason=NULL
        WHERE owner_user_id = :uid
          AND status='paused'
          AND paused_reason='billing'
        """
        return await db_execute(q, {"uid": int(owner_user_id)})


class ModuleRepo:
    @staticmethod
    async def list_enabled(tenant_id: str) -> list[str]:
        q = """
        SELECT module_key
        FROM tenant_modules
        WHERE tenant_id = :tid AND enabled = true
        ORDER BY module_key
        """
        rows = await db_fetch_all(q, {"tid": tenant_id})
        return [r["module_key"] for r in rows]

    @staticmethod
    async def enable(tenant_id: str, module_key: str) -> None:
        q = """
        INSERT INTO tenant_modules (tenant_id, module_key, enabled)
        VALUES (:tid, :mk, true)
        ON CONFLICT (tenant_id, module_key)
        DO UPDATE SET enabled = true
        """
        await db_execute(q, {"tid": tenant_id, "mk": module_key})

    @staticmethod
    async def disable(tenant_id: str, module_key: str) -> None:
        q = """
        UPDATE tenant_modules
        SET enabled = false
        WHERE tenant_id = :tid AND module_key = :mk
        """
        await db_execute(q, {"tid": tenant_id, "mk": module_key})

    @staticmethod
    async def ensure_defaults(tenant_id: str, product_key: str | None = None) -> None:
        """
        core — завжди
        product_key — якщо оренда через маркетплейс, то увімкнути модуль продукту
        fallback — якщо руками додали токен без продукту -> shop
        """
        await ModuleRepo.enable(tenant_id, "core")

        if product_key:
            await ModuleRepo.enable(tenant_id, product_key)
        else:
            await ModuleRepo.enable(tenant_id, "shop")

    @staticmethod
    async def list_all(tenant_id: str) -> list[dict]:
        q = """
        SELECT module_key, enabled
        FROM tenant_modules
        WHERE tenant_id = :tid
        ORDER BY module_key
        """
        rows = await db_fetch_all(q, {"tid": tenant_id})
        return [{"module_key": r["module_key"], "enabled": bool(r["enabled"])} for r in rows]


class TenantSecretRepo:
    @staticmethod
    async def list_keys(tenant_id: str) -> list[str]:
        q = """
        SELECT secret_key
        FROM tenant_secrets
        WHERE tenant_id = :tid
        ORDER BY secret_key
        """
        rows = await db_fetch_all(q, {"tid": tenant_id})
        return [r["secret_key"] for r in rows]

    @staticmethod
    async def get(tenant_id: str, secret_key: str) -> dict | None:
        q = """
        SELECT tenant_id, secret_key, secret_value, updated_ts
        FROM tenant_secrets
        WHERE tenant_id = :tid AND secret_key = :k
        """
        return await db_fetch_one(q, {"tid": tenant_id, "k": secret_key})

    @staticmethod
    async def upsert(tenant_id: str, secret_key: str, secret_value: str) -> None:
        q = """
        INSERT INTO tenant_secrets (tenant_id, secret_key, secret_value, updated_ts)
        VALUES (:tid, :k, :v, :ts)
        ON CONFLICT (tenant_id, secret_key)
        DO UPDATE SET secret_value = EXCLUDED.secret_value, updated_ts = EXCLUDED.updated_ts
        """
        await db_execute(q, {"tid": tenant_id, "k": secret_key, "v": secret_value, "ts": int(time.time())})

    @staticmethod
    async def delete(tenant_id: str, secret_key: str) -> None:
        q = """
        DELETE FROM tenant_secrets
        WHERE tenant_id = :tid AND secret_key = :k
        """
        await db_execute(q, {"tid": tenant_id, "k": secret_key})

class TenantIntegrationRepo:
    @staticmethod
    async def list_all(tenant_id: str) -> list[dict]:
        q = """
        SELECT provider, enabled, updated_ts
        FROM tenant_integrations
        WHERE tenant_id = :tid
        ORDER BY provider
        """
        rows = await db_fetch_all(q, {"tid": tenant_id})
        return [
            {"provider": r["provider"], "enabled": bool(r["enabled"]), "updated_ts": int(r.get("updated_ts") or 0)}
            for r in rows
        ]

    @staticmethod
    async def get(tenant_id: str, provider: str) -> dict | None:
        q = """
        SELECT provider, enabled, updated_ts
        FROM tenant_integrations
        WHERE tenant_id = :tid AND provider = :p
        """
        return await db_fetch_one(q, {"tid": tenant_id, "p": provider})

    @staticmethod
    async def set_enabled(tenant_id: str, provider: str, enabled: bool) -> None:
        q = """
        INSERT INTO tenant_integrations (tenant_id, provider, enabled, updated_ts)
        VALUES (:tid, :p, :en, :ts)
        ON CONFLICT (tenant_id, provider)
        DO UPDATE SET enabled = EXCLUDED.enabled, updated_ts = EXCLUDED.updated_ts
        """
        await db_execute(q, {"tid": tenant_id, "p": provider, "en": bool(enabled), "ts": int(time.time())})


class AccountRepo:
    @staticmethod
    async def ensure(owner_user_id: int) -> None:
        q = """
        INSERT INTO owner_accounts (owner_user_id, balance_kop, withdraw_balance_kop, updated_ts)
        VALUES (:uid, 0, 0, :ts)
        ON CONFLICT (owner_user_id) DO NOTHING
        """
        await db_execute(q, {"uid": int(owner_user_id), "ts": int(time.time())})

    @staticmethod
    async def get(owner_user_id: int) -> dict | None:
        q = """
        SELECT owner_user_id, balance_kop, withdraw_balance_kop, updated_ts
        FROM owner_accounts
        WHERE owner_user_id = :uid
        """
        return await db_fetch_one(q, {"uid": int(owner_user_id)})

    @staticmethod
    async def add_balance(owner_user_id: int, delta_kop: int) -> None:
        await AccountRepo.ensure(owner_user_id)
        q = """
        UPDATE owner_accounts
        SET balance_kop = balance_kop + :d,
            updated_ts = :ts
        WHERE owner_user_id = :uid
        """
        await db_execute(q, {"uid": int(owner_user_id), "d": int(delta_kop), "ts": int(time.time())})

    @staticmethod
    async def set_balance(owner_user_id: int, new_balance_kop: int) -> None:
        await AccountRepo.ensure(owner_user_id)
        q = """
        UPDATE owner_accounts
        SET balance_kop = :b,
            updated_ts = :ts
        WHERE owner_user_id = :uid
        """
        await db_execute(q, {"uid": int(owner_user_id), "b": int(new_balance_kop), "ts": int(time.time())})

    @staticmethod
    async def add_withdraw_balance(owner_user_id: int, delta_kop: int) -> None:
        await AccountRepo.ensure(owner_user_id)
        q = """
        UPDATE owner_accounts
        SET withdraw_balance_kop = withdraw_balance_kop + :d,
            updated_ts = :ts
        WHERE owner_user_id = :uid
        """
        await db_execute(q, {"uid": int(owner_user_id), "d": int(delta_kop), "ts": int(time.time())})

    @staticmethod
    async def set_withdraw_balance(owner_user_id: int, new_withdraw_kop: int) -> None:
        await AccountRepo.ensure(owner_user_id)
        q = """
        UPDATE owner_accounts
        SET withdraw_balance_kop = :w,
            updated_ts = :ts
        WHERE owner_user_id = :uid
        """
        await db_execute(q, {"uid": int(owner_user_id), "w": int(new_withdraw_kop), "ts": int(time.time())})

    @staticmethod
    async def charge_with_ledger(
        owner_user_id: int,
        charge_kop: int,
        min_balance_kop: int,
        kind: str,
        tenant_id: str | None,
        meta_json: str,
        created_ts: int,
    ) -> int | None:
        """
        Атомарно: (1) списати баланс з лімітом, (2) додати ledger.
        Повертає новий balance_kop або None якщо не вистачає.
        meta_json — вже json.dumps(...)
        """
        await AccountRepo.ensure(owner_user_id)
        q = """
        WITH updated AS (
          UPDATE owner_accounts
          SET balance_kop = balance_kop - :c,
              updated_ts = :ts
          WHERE owner_user_id = :uid
            AND (balance_kop - :c) >= :min_bal
          RETURNING balance_kop
        )
        INSERT INTO billing_ledger (owner_user_id, tenant_id, kind, amount_kop, meta, created_ts)
        SELECT :uid, :tid, :k, :amount, :m, :ts
        FROM updated
        RETURNING (SELECT balance_kop FROM updated) AS balance_kop
        """
        row = await db_fetch_one(
            q,
            {
                "uid": int(owner_user_id),
                "c": int(charge_kop),
                "min_bal": int(min_balance_kop),
                "ts": int(created_ts),
                "tid": tenant_id,
                "k": str(kind),
                "amount": -int(charge_kop),
                "m": meta_json,
            },
        )
        return int(row["balance_kop"]) if row and row.get("balance_kop") is not None else None

    @staticmethod
    async def try_charge(owner_user_id: int, charge_kop: int, min_balance_kop: int) -> int | None:
        await AccountRepo.ensure(owner_user_id)
        q = """
        UPDATE owner_accounts
        SET balance_kop = balance_kop - :c,
            updated_ts = :ts
        WHERE owner_user_id = :uid
          AND (balance_kop - :c) >= :min_bal
        RETURNING balance_kop
        """
        row = await db_fetch_one(q, {
            "uid": int(owner_user_id),
            "c": int(charge_kop),
            "min_bal": int(min_balance_kop),
            "ts": int(time.time()),
        })
        return int(row["balance_kop"]) if row else None


class LedgerRepo:

    @staticmethod
    async def list_last(owner_user_id: int, limit: int = 10) -> list[dict]:
        q = """
        SELECT kind, amount_kop, tenant_id, meta, created_ts
        FROM billing_ledger
        WHERE owner_user_id = :uid
        ORDER BY created_ts DESC
        LIMIT :lim
        """
        return await db_fetch_all(q, {"uid": int(owner_user_id), "lim": int(limit)})


    @staticmethod
    async def has_topup_invoice(owner_user_id: int, invoice_id: int) -> bool:
        q = """
        SELECT 1
        FROM billing_ledger
        WHERE owner_user_id = :uid
          AND kind = 'topup'
          AND (meta::jsonb ->> 'invoice_id') = :iid
        LIMIT 1
        """
        row = await db_fetch_one(q, {"uid": int(owner_user_id), "iid": str(int(invoice_id))})
        return bool(row)

    @staticmethod
    async def add(
        owner_user_id: int,
        kind: str,
        amount_kop: int,
        tenant_id: str | None = None,
        meta: dict | None = None,
    ) -> None:
        q = """
        INSERT INTO billing_ledger (owner_user_id, tenant_id, kind, amount_kop, meta, created_ts)
        VALUES (:uid, :tid, :k, :a, :m, :ts)
        """
        await db_execute(
            q,
            {
                "uid": int(owner_user_id),
                "tid": tenant_id,
                "k": str(kind),
                "a": int(amount_kop),
                "m": json.dumps(meta or {}, ensure_ascii=False),
                "ts": int(time.time()),
            },
        )


import logging
log = logging.getLogger(__name__)

class InvoiceRepo:
    TABLE = "billing_invoices"

    @staticmethod
    async def create(owner_user_id: int, provider: str, amount_kop: int, pay_url: str, meta: dict | None = None) -> dict[str, Any]:
        ts = int(time.time())
        q = f"""
        INSERT INTO {InvoiceRepo.TABLE} (
            owner_user_id, provider, amount_kop,
            status, pay_url, meta, created_ts, paid_ts
        )
        VALUES (:uid, :p, :a, 'pending', :url, :m, :ts, 0)
        RETURNING id, owner_user_id, provider, amount_kop, pay_url, status, meta, created_ts, paid_ts
        """
        row = await db_fetch_one(
            q,
            {
                "uid": int(owner_user_id),
                "p": str(provider),
                "a": int(amount_kop),
                "url": str(pay_url),
                "m": json.dumps(meta or {}, ensure_ascii=False),
                "ts": ts,
            },
        )
        return row or {}

    @staticmethod
    async def get_for_owner(owner_user_id: int, invoice_id: int) -> dict | None:
        q = f"""
        SELECT id, owner_user_id, provider, amount_kop, pay_url, status, meta, created_ts, paid_ts
        FROM {InvoiceRepo.TABLE}
        WHERE id = :id AND owner_user_id = :uid
        """
        return await db_fetch_one(q, {"id": int(invoice_id), "uid": int(owner_user_id)})

    @staticmethod
    async def mark_paid(owner_user_id: int, invoice_id: int) -> None:
        q = f"""
        UPDATE {InvoiceRepo.TABLE}
        SET status = 'paid',
            paid_ts = :ts
        WHERE id = :id AND owner_user_id = :uid AND status = 'pending'
        """
        await db_execute(q, {"id": int(invoice_id), "uid": int(owner_user_id), "ts": int(time.time())})

class WithdrawRepo:
    TABLE = "withdraw_requests"

    @staticmethod
    async def create(owner_user_id: int, amount_kop: int, method: str = "manual", meta: dict | None = None) -> dict:
        ts = int(time.time())
        q = f"""
        INSERT INTO {WithdrawRepo.TABLE} (
            owner_user_id, amount_kop, method,
            status, meta, created_ts, updated_ts
        )
        VALUES (:uid, :a, :m, 'pending', :meta, :ts, :ts)
        RETURNING id, owner_user_id, amount_kop, method, status, meta, created_ts, updated_ts
        """
        row = await db_fetch_one(
            q,
            {
                "uid": int(owner_user_id),
                "a": int(amount_kop),
                "m": str(method),
                "meta": json.dumps(meta or {}, ensure_ascii=False),
                "ts": ts,
            },
        )
        return row or {}

    @staticmethod
    async def get_for_owner(owner_user_id: int, withdraw_id: int) -> dict | None:
        q = f"""
        SELECT id, owner_user_id, amount_kop, method, status, meta, created_ts, updated_ts
        FROM {WithdrawRepo.TABLE}
        WHERE id = :id AND owner_user_id = :uid
        """
        return await db_fetch_one(q, {"id": int(withdraw_id), "uid": int(owner_user_id)})

    @staticmethod
    async def list_for_owner(owner_user_id: int, limit: int = 20) -> list[dict]:
        q = f"""
        SELECT id, owner_user_id, amount_kop, method, status, meta, created_ts, updated_ts
        FROM {WithdrawRepo.TABLE}
        WHERE owner_user_id = :uid
        ORDER BY created_ts DESC
        LIMIT :lim
        """
        return await db_fetch_all(q, {"uid": int(owner_user_id), "lim": int(limit)})

    @staticmethod
    async def set_status(withdraw_id: int, status: str) -> None:
        q = f"""
        UPDATE {WithdrawRepo.TABLE}
        SET status = :st,
            updated_ts = :ts
        WHERE id = :id
        """
        await db_execute(q, {"id": int(withdraw_id), "st": str(status), "ts": int(time.time())})

import asyncio
from datetime import datetime, timedelta, timezone

BILLING_NEGATIVE_LIMIT_KOP = -300  # -3 грн
BILLING_MAX_MINUTES_PER_DAY = 24 * 60

def _floor_minutes(a_ts: int, b_ts: int) -> int:
    if b_ts <= a_ts:
        return 0
    return max(0, int((b_ts - a_ts) // 60))

async def _try_charge_owner_balance(owner_user_id: int, charge_kop: int) -> bool:
    """
    Atomic списання з лімітом мінуса до -3 грн.
    """
    await AccountRepo.ensure(owner_user_id)
    q = """
    UPDATE owner_accounts
    SET balance_kop = balance_kop - :c,
        updated_ts = :ts
    WHERE owner_user_id = :uid
      AND (balance_kop - :c) >= :min_bal
    RETURNING balance_kop
    """
    row = await db_fetch_one(
        q,
        {"uid": int(owner_user_id), "c": int(charge_kop), "ts": int(time.time()), "min_bal": int(BILLING_NEGATIVE_LIMIT_KOP)},
    )
    return bool(row)

async def run_daily_billing(now_ts: int | None = None) -> dict[str, Any]:
    """
    Запускати 1 раз на добу о 00:00.
    Повертає статистику (для логів/адмінки).
    """
    now_ts = int(now_ts or time.time())
    tenants = await TenantRepo.list_active_for_billing()

    charged_total_kop = 0
    charged_cnt = 0
    paused_cnt = 0

    for t in tenants:
        tenant_id = t["id"]
        owner_user_id = int(t["owner_user_id"])
        rate = int(t.get("rate_per_min_kop") or 0)
        last_billed_ts = int(t.get("last_billed_ts") or 0)

        if rate <= 0:
            # якщо тариф ще не проставили — просто синхронізуємо last_billed_ts, щоб не накопичувалось
            await TenantRepo.set_rate_and_last_billed(owner_user_id, tenant_id, rate_per_min_kop=0, last_billed_ts=now_ts)
            continue

        minutes = _floor_minutes(last_billed_ts, now_ts)
        if minutes <= 0:
            continue

        if minutes > BILLING_MAX_MINUTES_PER_DAY:
            minutes = BILLING_MAX_MINUTES_PER_DAY

        charge_kop = int(minutes * rate)
        if charge_kop <= 0:
            await TenantRepo.set_rate_and_last_billed(owner_user_id, tenant_id, rate_per_min_kop=rate, last_billed_ts=now_ts)
            continue

        ok = await _try_charge_owner_balance(owner_user_id, charge_kop)
        if not ok:
            # не вистачає — ставимо на паузу billing
            await TenantRepo.system_pause_billing(tenant_id)
            paused_cnt += 1
            try:
                await LedgerRepo.add(
                    owner_user_id,
                    "billing_paused",
                    0,
                    tenant_id=tenant_id,
                    meta={"reason": "insufficient_funds"},
                )
            except Exception:
                pass
            continue

        # списали успішно
        charged_total_kop += charge_kop
        charged_cnt += 1

        await TenantRepo.set_rate_and_last_billed(owner_user_id, tenant_id, rate_per_min_kop=rate, last_billed_ts=now_ts)

        try:
            await LedgerRepo.add(
                owner_user_id,
                "daily_tariff",
                -charge_kop,
                tenant_id=tenant_id,
                meta={"minutes": minutes, "rate_per_min_kop": rate, "charged_kop": charge_kop, "ts": now_ts},
            )
        except Exception:
            pass

    return {
        "now_ts": now_ts,
        "charged_cnt": charged_cnt,
        "charged_total_kop": charged_total_kop,
        "paused_cnt": paused_cnt,
    }

async def billing_daemon_daily_midnight() -> None:
    """
    Фоновий демон: чекає до наступної 00:00 і робить run_daily_billing().
    """
    while True:
        # UTC+2/UTC+3 у тебе плаває — краще брати локальний server time як є.
        now = datetime.now()
        tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        sleep_s = max(1, int((tomorrow - now).total_seconds()))
        await asyncio.sleep(sleep_s)

        try:
            res = await run_daily_billing(int(time.time()))
            log.info("DAILY BILLING: %s", res)
        except Exception as e:
            log.exception("DAILY BILLING FAILED: %s", e)
class PlatformSettingsRepo:
    TABLE = "platform_settings"

    @staticmethod
    async def get() -> dict | None:
        q = f"""
        SELECT id, cabinet_banner_url, ref_json, updated_ts
        FROM platform_settings
        WHERE id = 1
        """
        return await db_fetch_one(q, {})

    @staticmethod
    async def upsert_cabinet_banner(url: str) -> None:
        q = f"""
        INSERT INTO {PlatformSettingsRepo.TABLE} (id, cabinet_banner_url, updated_ts)
        VALUES (1, :u, :ts)
        ON CONFLICT (id)
        DO UPDATE SET cabinet_banner_url = EXCLUDED.cabinet_banner_url,
                      updated_ts = EXCLUDED.updated_ts
        """
        await db_execute(q, {"u": (url or "").strip(), "ts": int(time.time())})

    # ✅ ДОДАТИ ОЦЕ:
    @staticmethod
    async def get_ref_settings() -> dict:
        row = await PlatformSettingsRepo.get()
        raw = (row.get("ref_json") if row else "") or ""
        try:
            return json.loads(raw) if raw.strip() else {}
        except Exception:
            return {}

    @staticmethod
    async def set_ref_settings(payload: dict) -> None:
        # гарантуємо рядок id=1
        q = f"""
        INSERT INTO {PlatformSettingsRepo.TABLE} (id, cabinet_banner_url, ref_json, updated_ts)
        VALUES (1, COALESCE((SELECT cabinet_banner_url FROM platform_settings WHERE id=1), ''), :rj, :ts)
        ON CONFLICT (id)
        DO UPDATE SET ref_json = EXCLUDED.ref_json,
                      updated_ts = EXCLUDED.updated_ts
        """
        await db_execute(q, {"rj": json.dumps(payload or {}, ensure_ascii=False), "ts": int(time.time())})

    @staticmethod
    async def get_marketplace_overrides() -> dict:
        row = await PlatformSettingsRepo.get()
        raw = (row.get("ref_json") if row else "") or ""
        try:
            data = json.loads(raw) if raw.strip() else {}
        except Exception:
            data = {}
        ov = data.get("marketplace_overrides") or {}
        return ov if isinstance(ov, dict) else {}

    @staticmethod
    async def set_marketplace_overrides(overrides: dict) -> None:
        row = await PlatformSettingsRepo.get()
        raw = (row.get("ref_json") if row else "") or ""
        try:
            data = json.loads(raw) if raw.strip() else {}
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}

        data["marketplace_overrides"] = overrides if isinstance(overrides, dict) else {}

        q = f"""
        INSERT INTO {PlatformSettingsRepo.TABLE} (id, cabinet_banner_url, ref_json, updated_ts)
        VALUES (
            1,
            COALESCE((SELECT cabinet_banner_url FROM {PlatformSettingsRepo.TABLE} WHERE id=1), ''),
            :rj,
            :ts
        )
        ON CONFLICT (id)
        DO UPDATE SET ref_json = EXCLUDED.ref_json,
                      updated_ts = EXCLUDED.updated_ts
        """
        await db_execute(q, {"rj": json.dumps(data, ensure_ascii=False), "ts": int(time.time())})

class ReferralRepo:
    @staticmethod
    async def bind(user_id: int, referrer_id: int) -> bool:
        """
        Прив'язуємо реферала один раз (user_id -> referrer_id).
        Повертає True якщо прив'язали, False якщо вже було/не можна.
        """
        user_id = int(user_id)
        referrer_id = int(referrer_id)

        if user_id <= 0 or referrer_id <= 0:
            return False
        if user_id == referrer_id:
            return False

        q = """
        INSERT INTO ref_users (user_id, referrer_id, created_ts)
        VALUES (:u, :r, :ts)
        ON CONFLICT (user_id) DO NOTHING
        """
        await db_execute(q, {"u": user_id, "r": referrer_id, "ts": int(time.time())})

        row = await db_fetch_one(
            "SELECT 1 FROM ref_users WHERE user_id = :u AND referrer_id = :r",
            {"u": user_id, "r": referrer_id},
        )
        return bool(row)

    @staticmethod
    async def get_referrer(user_id: int) -> int | None:
        row = await db_fetch_one("SELECT referrer_id FROM ref_users WHERE user_id = :u", {"u": int(user_id)})
        return int(row["referrer_id"]) if row else None

    @staticmethod
    async def get_settings() -> dict:
        """
        Беремо ref_json з platform_settings(id=1).
        Якщо пусто — дефолти.
        """
        row = await PlatformSettingsRepo.get()
        raw = (row.get("ref_json") if row else "") or ""
        try:
            data = json.loads(raw) if raw.strip() else {}
        except Exception:
            data = {}

        return {
            "enabled": bool(data.get("enabled", True)),
            "percent_topup_bps": int(data.get("percent_topup_bps", 500)),     # 5%
            "percent_billing_bps": int(data.get("percent_billing_bps", 200)), # 2%
            "min_payout_kop": int(data.get("min_payout_kop", 10000)),         # 100 грн
        }

    @staticmethod
    async def set_settings(payload: dict) -> None:
        """
        Часткове оновлення ref_json (merge), щоб не затерти marketplace_overrides та інші поля.
        """
        row = await PlatformSettingsRepo.get()
        raw = (row.get("ref_json") if row else "") or ""

        try:
            cur = json.loads(raw) if raw.strip() else {}
        except Exception:
            cur = {}

        if not isinstance(cur, dict):
            cur = {}

        # оновлюємо ТІЛЬКИ поля рефералки
        cur["enabled"] = bool(payload.get("enabled", True))
        cur["percent_topup_bps"] = int(payload.get("percent_topup_bps", 500))
        cur["percent_billing_bps"] = int(payload.get("percent_billing_bps", 200))
        cur["min_payout_kop"] = int(payload.get("min_payout_kop", 10000))

        q = f"""
        INSERT INTO {PlatformSettingsRepo.TABLE} (id, cabinet_banner_url, ref_json, updated_ts)
        VALUES (1, COALESCE((SELECT cabinet_banner_url FROM {PlatformSettingsRepo.TABLE} WHERE id=1), ''), :rj, :ts)
        ON CONFLICT (id)
        DO UPDATE SET ref_json = EXCLUDED.ref_json, updated_ts = EXCLUDED.updated_ts
        """
        await db_execute(q, {"rj": json.dumps(cur, ensure_ascii=False), "ts": int(time.time())})

    @staticmethod
    async def _ensure_balance(referrer_id: int) -> None:
        q = """
        INSERT INTO ref_balances (referrer_id, available_kop, total_earned_kop, total_paid_kop, updated_ts)
        VALUES (:r, 0, 0, 0, :ts)
        ON CONFLICT (referrer_id) DO NOTHING
        """
        await db_execute(q, {"r": int(referrer_id), "ts": int(time.time())})

    @staticmethod
    async def get_balance(referrer_id: int) -> dict | None:
        await ReferralRepo._ensure_balance(referrer_id)
        q = """
        SELECT referrer_id, available_kop, total_earned_kop, total_paid_kop, updated_ts
        FROM ref_balances
        WHERE referrer_id = :r
        """
        return await db_fetch_one(q, {"r": int(referrer_id)})

    # далі — твій apply_commission/stats без змін

  
    @staticmethod
    async def _try_mark_event_once(event_key: str) -> bool:
        """
        Idempotency: якщо event_key вже був — не нараховуємо вдруге.
        """
        ek = (event_key or "").strip()[:128]
        if not ek:
            return False

        q = """
        INSERT INTO ref_applied_events (event_key, created_ts)
        VALUES (:k, :ts)
        ON CONFLICT (event_key) DO NOTHING
        """
        await db_execute(q, {"k": ek, "ts": int(time.time())})

        row = await db_fetch_one("SELECT 1 FROM ref_applied_events WHERE event_key = :k", {"k": ek})
        return bool(row)

    @staticmethod
    async def apply_commission(
        user_id: int,
        kind: str,
        amount_kop: int,
        event_key: str,
        title: str = "",
        details: str = "",
    ) -> int:
        """
        Нарахувати партнерку рефереру цього user_id.
        kind: 'topup' або 'billing'
        amount_kop: позитивне число (скільки user заплатив/було списано)
        event_key: унікальний ключ події (щоб не нарахувати двічі)
        """
        user_id = int(user_id)
        amount_kop = int(amount_kop)

        if amount_kop <= 0:
            return 0

        settings = await ReferralRepo.get_settings()
        if not settings["enabled"]:
            return 0

        referrer_id = await ReferralRepo.get_referrer(user_id)
        if not referrer_id or referrer_id == user_id:
            return 0

        # idempotency: якщо вже застосовано — виходимо
        # але! _try_mark_event_once поверне True навіть якщо був раніше.
        # нам треба відрізнити "щойно вставив" чи "вже було":
        # простий варіант — спочатку перевірити існування.
        existed = await db_fetch_one("SELECT 1 FROM ref_applied_events WHERE event_key = :k", {"k": event_key})
        if existed:
            return 0

        ok_mark = await ReferralRepo._try_mark_event_once(event_key)
        if not ok_mark:
            return 0

        bps = settings["percent_topup_bps"] if kind == "topup" else settings["percent_billing_bps"]
        bps = max(0, int(bps))

        commission = (amount_kop * bps) // 10000
        if commission <= 0:
            return 0

        await ReferralRepo._ensure_balance(referrer_id)

        # баланс партнера
        q = """
        UPDATE ref_balances
        SET available_kop = available_kop + :c,
            total_earned_kop = total_earned_kop + :c,
            updated_ts = :ts
        WHERE referrer_id = :r
        """
        await db_execute(q, {"c": int(commission), "ts": int(time.time()), "r": int(referrer_id)})

        # ledger
        ql = """
        INSERT INTO ref_ledger (referrer_id, user_id, kind, amount_kop, title, details, created_ts)
        VALUES (:r, :u, :k, :a, :t, :d, :ts)
        """
        await db_execute(
            ql,
            {
                "r": int(referrer_id),
                "u": int(user_id),
                "k": str(kind),
                "a": int(commission),
                "t": (title or "")[:128],
                "d": (details or "")[:512],
                "ts": int(time.time()),
            },
        )

        return int(commission)

    @staticmethod
    async def stats(referrer_id: int) -> dict:
        referrer_id = int(referrer_id)
        bal = await ReferralRepo.get_balance(referrer_id) or {}

        q = "SELECT COUNT(*) AS cnt FROM ref_users WHERE referrer_id = :r"
        row = await db_fetch_one(q, {"r": referrer_id})
        refs_cnt = int(row["cnt"]) if row else 0

        q2 = """
        SELECT kind, COALESCE(SUM(amount_kop),0) AS s
        FROM ref_ledger
        WHERE referrer_id = :r
        GROUP BY kind
        """
        rows = await db_fetch_all(q2, {"r": referrer_id})
        by_kind = {r["kind"]: int(r["s"]) for r in (rows or [])}

        return {
            "referrer_id": referrer_id,
            "refs_cnt": refs_cnt,
            "available_kop": int(bal.get("available_kop") or 0),
            "total_earned_kop": int(bal.get("total_earned_kop") or 0),
            "total_paid_kop": int(bal.get("total_paid_kop") or 0),
            "by_kind": by_kind,
        }


class RefPayoutRepo:
    @staticmethod
    async def list_pending(limit: int = 20) -> list[dict]:
        q = """
        SELECT id, referrer_id, amount_kop, status, note, created_ts
        FROM ref_payout_requests
        WHERE status = 'pending'
        ORDER BY created_ts ASC
        LIMIT :lim
        """
        return await db_fetch_all(q, {"lim": int(limit)})

    @staticmethod
    async def approve(request_id: int) -> bool:
        # pending -> approved, плюс total_paid_kop
        q = """
        UPDATE ref_payout_requests
        SET status = 'approved'
        WHERE id = :id AND status = 'pending'
        RETURNING referrer_id, amount_kop
        """
        row = await db_fetch_one(q, {"id": int(request_id)})
        if not row:
            return False

        referrer_id = int(row["referrer_id"])
        amount_kop = int(row["amount_kop"])

        q2 = """
        UPDATE ref_balances
        SET total_paid_kop = total_paid_kop + :a,
            updated_ts = :ts
        WHERE referrer_id = :r
        """
        await db_execute(q2, {"a": amount_kop, "r": referrer_id, "ts": int(time.time())})

        # ledger запис (службовий)
        ql = """
        INSERT INTO ref_ledger (referrer_id, user_id, kind, amount_kop, title, details, created_ts)
        VALUES (:r, NULL, 'payout_approved', :a, :t, :d, :ts)
        """
        await db_execute(ql, {
            "r": referrer_id,
            "a": -amount_kop,
            "t": "Виплата підтверджена",
            "d": f"request_id={int(request_id)}",
            "ts": int(time.time()),
        })

        return True

    @staticmethod
    async def reject(request_id: int, reason: str = "") -> bool:
        # pending -> rejected, і повертаємо гроші в available_kop
        q = """
        UPDATE ref_payout_requests
        SET status = 'rejected'
        WHERE id = :id AND status = 'pending'
        RETURNING referrer_id, amount_kop
        """
        row = await db_fetch_one(q, {"id": int(request_id)})
        if not row:
            return False

        referrer_id = int(row["referrer_id"])
        amount_kop = int(row["amount_kop"])

        q2 = """
        UPDATE ref_balances
        SET available_kop = available_kop + :a,
            updated_ts = :ts
        WHERE referrer_id = :r
        """
        await db_execute(q2, {"a": amount_kop, "r": referrer_id, "ts": int(time.time())})

        ql = """
        INSERT INTO ref_ledger (referrer_id, user_id, kind, amount_kop, title, details, created_ts)
        VALUES (:r, NULL, 'payout_rejected', :a, :t, :d, :ts)
        """
        await db_execute(ql, {
            "r": referrer_id,
            "a": amount_kop,  # повернення
            "t": "Виплату відхилено",
            "d": (reason or f"request_id={int(request_id)}")[:512],
            "ts": int(time.time()),
        })

        return True

    @staticmethod
    async def create_request(referrer_id: int, amount_kop: int, note: str = "") -> dict | None:
        referrer_id = int(referrer_id)
        amount_kop = int(amount_kop)
        if amount_kop <= 0:
            return None

        settings = await ReferralRepo.get_settings()
        if amount_kop < int(settings["min_payout_kop"]):
            return None

        bal = await ReferralRepo.get_balance(referrer_id)
        if not bal:
            return None

        if int(bal.get("available_kop") or 0) < amount_kop:
            return None

        # списуємо з available одразу (reserve)
        q = """
        UPDATE ref_balances
        SET available_kop = available_kop - :a,
            updated_ts = :ts
        WHERE referrer_id = :r AND available_kop >= :a
        RETURNING available_kop
        """
        row = await db_fetch_one(q, {"a": amount_kop, "ts": int(time.time()), "r": referrer_id})
        if not row:
            return None

        # створюємо заявку
        q2 = """
        INSERT INTO ref_payout_requests (referrer_id, amount_kop, status, note, created_ts)
        VALUES (:r, :a, 'pending', :n, :ts)
        RETURNING id, referrer_id, amount_kop, status, note, created_ts
        """
        req = await db_fetch_one(q2, {"r": referrer_id, "a": amount_kop, "n": (note or "")[:256], "ts": int(time.time())})

        # ledger мінус
        ql = """
        INSERT INTO ref_ledger (referrer_id, user_id, kind, amount_kop, title, details, created_ts)
        VALUES (:r, NULL, 'payout_request', :a, :t, :d, :ts)
        """
        await db_execute(ql, {
            "r": referrer_id,
            "a": -amount_kop,
            "t": "Заявка на виплату",
            "d": f"request_id={req['id'] if req else 0}",
            "ts": int(time.time()),
        })

        return req