# rent_platform/db/repo.py
from __future__ import annotations

import secrets
import time
from typing import Any

from rent_platform.db.session import db_fetch_one, db_fetch_all, db_execute


class TenantRepo:
    @staticmethod
    async def get_by_id(tenant_id: str) -> dict | None:
        q = """
        SELECT id, owner_user_id, bot_token, secret, status, created_ts,
               plan_key, paid_until_ts, paused_reason
        FROM tenants
        WHERE id = :id
        """
        return await db_fetch_one(q, {"id": tenant_id})

    @staticmethod
    async def list_by_owner(owner_user_id: int) -> list[dict[str, Any]]:
        q = """
        SELECT id, bot_token, secret, status, created_ts,
               plan_key, paid_until_ts, paused_reason
        FROM tenants
        WHERE owner_user_id = :uid
        ORDER BY created_ts DESC
        """
        rows = await db_fetch_all(q, {"uid": owner_user_id})
        return [
            {
                "id": r["id"],
                "name": "Bot",
                "token": r["bot_token"],   # ⚠️ у UI не показуємо
                "secret": r["secret"],     # ⚠️ у UI не показуємо
                "status": r["status"],
                "plan_key": r.get("plan_key") or "free",
                "paid_until_ts": int(r.get("paid_until_ts") or 0),
                "paused_reason": r.get("paused_reason"),
            }
            for r in rows
        ]

    @staticmethod
    async def create(owner_user_id: int, bot_token: str) -> dict[str, Any]:
        tenant_id = secrets.token_hex(4)
        secret = secrets.token_urlsafe(24)
        created_ts = int(time.time())

        q = """
        INSERT INTO tenants (id, owner_user_id, bot_token, secret, status, created_ts, plan_key, paid_until_ts)
        VALUES (:id, :uid, :token, :secret, 'active', :ts, 'free', 0)
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
        }

    @staticmethod
    async def get_token_secret_for_owner(owner_user_id: int, tenant_id: str) -> dict | None:
        q = """
        SELECT id, bot_token, secret, status, plan_key, paid_until_ts, paused_reason
        FROM tenants
        WHERE id = :id AND owner_user_id = :uid
        """
        return await db_fetch_one(q, {"id": tenant_id, "uid": owner_user_id})

    @staticmethod
    async def set_status(
        owner_user_id: int,
        tenant_id: str,
        status: str,
        paused_reason: str | None = None,
    ) -> bool:
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
    async def set_paid_until(
        owner_user_id: int,
        tenant_id: str,
        paid_until_ts: int,
        plan_key: str = "basic",
    ) -> bool:
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
    async def list_all(tenant_id: str) -> list[dict]:
        q = """
        SELECT module_key, enabled
        FROM tenant_modules
        WHERE tenant_id = :tid
        ORDER BY module_key
        """
        rows = await db_fetch_all(q, {"tid": tenant_id})
        return [{"module_key": r["module_key"], "enabled": bool(r["enabled"])} for r in rows]

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
    async def ensure_defaults(tenant_id: str) -> None:
        # мінімум: core + shop
        await ModuleRepo.enable(tenant_id, "core")
        await ModuleRepo.enable(tenant_id, "shop")