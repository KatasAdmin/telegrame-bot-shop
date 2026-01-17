# rent_platform/core/webhook.py

import httpx
from rent_platform.core.tenant_ctx import get_tenant
from rent_platform.core.registry import get_module


async def handle_webhook(tenant_id: str, update: dict):
    tenant = get_tenant(tenant_id)

    message = update.get("message") or update.get("callback_query", {}).get("message")
    if not message:
        return

    text = message.get("text", "")

    # роутинг по модулях
    for module_name in tenant.active_modules:
        module = get_module(module_name)
        if module:
            handled = await module(tenant, update)
            if handled:
                return