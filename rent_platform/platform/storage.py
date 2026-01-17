from __future__ import annotations

from rent_platform.db.session import SessionLocal
from rent_platform.db.repo import list_tenants_by_owner, create_tenant, delete_tenant


async def list_bots(user_id: int) -> list[dict]:
    async with SessionLocal() as session:
        return await list_tenants_by_owner(session, user_id)


async def add_bot(user_id: int, token: str, name: str = "Bot") -> dict:
    async with SessionLocal() as session:
        return await create_tenant(session, owner_user_id=user_id, bot_token=token, name=name)


async def delete_bot(user_id: int, bot_id: str) -> bool:
    async with SessionLocal() as session:
        return await delete_tenant(session, owner_user_id=user_id, tenant_id=bot_id)