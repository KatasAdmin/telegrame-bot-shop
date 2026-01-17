from __future__ import annotations

import secrets
import time
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from rent_platform.db.models import Tenant


async def list_tenants_by_owner(session: AsyncSession, owner_user_id: int) -> list[dict[str, Any]]:
    res = await session.execute(
        select(Tenant).where(Tenant.owner_user_id == owner_user_id).order_by(Tenant.created_ts.desc())
    )
    items = res.scalars().all()
    return [{"id": t.id, "name": "Bot", "token": t.bot_token, "secret": t.secret, "status": t.status} for t in items]


async def create_tenant(session: AsyncSession, owner_user_id: int, bot_token: str, name: str = "Bot") -> dict[str, Any]:
    tenant_id = secrets.token_hex(4)   # короткий id як було
    secret = secrets.token_urlsafe(24)
    ts = int(time.time())

    t = Tenant(
        id=tenant_id,
        owner_user_id=owner_user_id,
        bot_token=bot_token,
        secret=secret,
        status="active",
        created_ts=ts,
    )
    session.add(t)
    await session.commit()

    return {"id": t.id, "name": name, "token": t.bot_token, "secret": t.secret, "status": t.status}


async def delete_tenant(session: AsyncSession, owner_user_id: int, tenant_id: str) -> bool:
    # видаляємо тільки якщо власник той самий
    res = await session.execute(
        select(Tenant.id).where(Tenant.id == tenant_id, Tenant.owner_user_id == owner_user_id)
    )
    ok = res.scalar_one_or_none() is not None
    if not ok:
        return False

    await session.execute(delete(Tenant).where(Tenant.id == tenant_id))
    await session.commit()
    return True