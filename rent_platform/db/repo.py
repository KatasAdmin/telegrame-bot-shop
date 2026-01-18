from __future__ import annotations

import secrets
import time
from typing import Any

from rent_platform.db.session import db_fetch_one, db_fetch_all, db_execute


class TenantRepo:
    @staticmethod
    async def get_by_id(tenant_id: str) -> dict | None:
        q = """
        SELECT id, owner_user_id, bot_token, secret, status, created_ts
        FROM tenants
        WHERE id = :id
        """
        return await db_fetch_one(q, {"id": tenant_id})

    @staticmethod
    async def list_by_owner(owner_user_id: int) -> list[dict[str, Any]]:
        q = """
        SELECT id, bot_token, secret, status, created_ts
        FROM tenants
        WHERE owner_user_id = :uid
        ORDER BY created_ts DESC
        """
        rows = await db_fetch_all(q, {"uid": owner_user_id})
        return [
            {
                "id": r["id"],
                "name": "Bot",  # пізніше додамо поле name
                "token": r["bot_token"],  # ⚠️ у UI не показуємо
                "secret": r["secret"],    # ⚠️ у UI не показуємо
                "status": r["status"],
            }
            for r in rows
        ]

    @staticmethod
    async def create(owner_user_id: int, bot_token: str) -> dict[str, Any]:
        tenant_id = secrets.token_hex(4)
        secret = secrets.token_urlsafe(24)
        created_ts = int(time.time())

        q = """
        INSERT INTO tenants (id, owner_user_id, bot_token, secret, status, created_ts)
        VALUES (:id, :uid, :token, :secret, 'active', :ts)
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
        }

    # ✅ потрібне для pause/resume/delete (щоб дістати токен/secret і переконатися що це власник)
    @staticmethod
    async def get_token_secret_for_owner(owner_user_id: int, tenant_id: str) -> dict | None:
        q = """
        SELECT id, bot_token, secret, status
        FROM tenants
        WHERE id = :id AND owner_user_id = :uid
        """
        return await db_fetch_one(q, {"id": tenant_id, "uid": owner_user_id})

    @staticmethod
    async def set_status(owner_user_id: int, tenant_id: str, status: str) -> bool:
        q = """
        UPDATE tenants
        SET status = :st
        WHERE id = :id AND owner_user_id = :uid
        """
        res = await db_execute(q, {"st": status, "id": tenant_id, "uid": owner_user_id})
        # db_execute у тебе може повертати rowcount або None.
        # Якщо None — просто перевіримо, що tenant існує.
        if res is None:
            exists = await TenantRepo.get_token_secret_for_owner(owner_user_id, tenant_id)
            return bool(exists)
        try:
            return int(res) > 0
        except Exception:
            return True

    # ✅ SOFT delete (нічого не видаляємо фізично)
    @staticmethod
    async def soft_delete(owner_user_id: int, tenant_id: str) -> bool:
        return await TenantRepo.set_status(owner_user_id, tenant_id, "deleted")


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
    async def ensure_defaults(tenant_id: str) -> None:
        await ModuleRepo.enable(tenant_id, "core")
        await ModuleRepo.enable(tenant_id, "shop")