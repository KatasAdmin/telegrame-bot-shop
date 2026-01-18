from __future__ import annotations

from aiogram import Bot

from rent_platform.config import settings
from rent_platform.db.repo import TenantRepo, ModuleRepo


def _tenant_webhook_url(tenant_id: str, secret: str) -> str:
    base = settings.WEBHOOK_URL.rstrip("/")
    prefix = settings.TENANT_WEBHOOK_PREFIX.rstrip("/")
    return f"{base}{prefix}/{tenant_id}/{secret}"


async def list_bots(user_id: int) -> list[dict]:
    return await TenantRepo.list_by_owner(user_id)


async def add_bot(user_id: int, token: str, name: str = "Bot") -> dict:
    # 1) створюємо tenant у БД
    tenant = await TenantRepo.create(owner_user_id=user_id, bot_token=token)

    # 2) дефолтні модулі (core + shop)
    await ModuleRepo.ensure_defaults(tenant["id"])

    # 3) ставимо webhook tenant-боту
    url = _tenant_webhook_url(tenant["id"], tenant["secret"])
    tenant_bot = Bot(token=token)
    try:
        await tenant_bot.set_webhook(
            url,
            drop_pending_updates=False,
            allowed_updates=["message", "callback_query"],
        )
    finally:
        await tenant_bot.session.close()

    # повертаємо те, що треба для UI
    return {"id": tenant["id"], "name": name, "status": tenant["status"]}


async def delete_bot(user_id: int, bot_id: str) -> bool:
    # (опційно) можна ще deleteWebhook, але на старті не критично
    return await TenantRepo.delete(owner_user_id=user_id, tenant_id=bot_id)