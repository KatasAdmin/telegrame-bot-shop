from __future__ import annotations

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from rent_platform.db.models import Tenant, TenantModule


async def create_tenant(
    db: AsyncSession,
    *,
    tenant_id: str,
    owner_user_id: int,
    bot_token: str,
    secret: str,
) -> Tenant:
    t = Tenant(id=tenant_id, owner_user_id=owner_user_id, bot_token=bot_token, secret=secret, status="active", created_ts=0)
    db.add(t)

    # дефолтні модулі: core + shop
    db.add(TenantModule(tenant_id=tenant_id, module_key="core", enabled=True))
    db.add(TenantModule(tenant_id=tenant_id, module_key="shop", enabled=True))

    await db.commit()
    await db.refresh(t)
    return t


async def get_tenant(db: AsyncSession, tenant_id: str) -> Tenant | None:
    res = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    return res.scalar_one_or_none()


async def get_tenant_enabled_modules(db: AsyncSession, tenant_id: str) -> list[str]:
    res = await db.execute(
        select(TenantModule.module_key)
        .where(TenantModule.tenant_id == tenant_id, TenantModule.enabled.is_(True))
    )
    return [r[0] for r in res.all()]


async def delete_tenant(db: AsyncSession, owner_user_id: int, tenant_id: str) -> bool:
    # захист: видаляє тільки власник
    res = await db.execute(select(Tenant).where(Tenant.id == tenant_id, Tenant.owner_user_id == owner_user_id))
    t = res.scalar_one_or_none()
    if not t:
        return False

    await db.execute(delete(Tenant).where(Tenant.id == tenant_id))
    await db.commit()
    return True