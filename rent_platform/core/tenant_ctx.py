# rent_platform/core/tenant_ctx.py

from dataclasses import dataclass


@dataclass
class TenantContext:
    tenant_id: str
    bot_token: str
    active_modules: list[str]
    is_active: bool = True


# ⚠️ ПОКИ in-memory (пізніше БД)
TENANTS: dict[str, TenantContext] = {}


def get_tenant(tenant_id: str) -> TenantContext:
    tenant = TENANTS.get(tenant_id)
    if not tenant:
        raise ValueError(f"Tenant {tenant_id} not found")
    return tenant


def register_tenant(
    tenant_id: str,
    bot_token: str,
    modules: list[str] | None = None
):
    TENANTS[tenant_id] = TenantContext(
        tenant_id=tenant_id,
        bot_token=bot_token,
        active_modules=modules or []
    )