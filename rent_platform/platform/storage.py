# rent_platform/platform/storage.py
from __future__ import annotations

import time
from typing import Any

from aiogram import Bot

from rent_platform.config import settings
from rent_platform.db.repo import TenantRepo, ModuleRepo


def _tenant_webhook_url(tenant_id: str, secret: str) -> str:
    base = settings.WEBHOOK_URL.rstrip("/")
    prefix = settings.TENANT_WEBHOOK_PREFIX.rstrip("/")
    return f"{base}{prefix}/{tenant_id}/{secret}"


# ======================================================================
# My bots
# ======================================================================

async def list_bots(user_id: int) -> list[dict]:
    return await TenantRepo.list_by_owner(user_id)


async def add_bot(user_id: int, token: str, name: str = "Bot") -> dict:
    tenant = await TenantRepo.create(owner_user_id=user_id, bot_token=token)

    # дефолтні модулі
    await ModuleRepo.ensure_defaults(tenant["id"])

    # виставляємо tenant webhook
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

    return {"id": tenant["id"], "name": name, "status": tenant["status"]}


async def pause_bot(user_id: int, bot_id: str) -> bool:
    row = await TenantRepo.get_token_secret_for_owner(user_id, bot_id)
    if not row:
        return False

    # ✅ paused_reason = manual
    ok = await TenantRepo.set_status(user_id, bot_id, "paused", paused_reason="manual")
    if not ok:
        return False

    # знімаємо webhook, щоб Telegram перестав слати апдейти
    tenant_bot = Bot(token=row["bot_token"])
    try:
        await tenant_bot.delete_webhook(drop_pending_updates=True)
    finally:
        await tenant_bot.session.close()

    return True


async def resume_bot(user_id: int, bot_id: str) -> bool:
    row = await TenantRepo.get_token_secret_for_owner(user_id, bot_id)
    if not row:
        return False

    # ✅ повертаємо в active + чистимо paused_reason
    ok = await TenantRepo.set_status(user_id, bot_id, "active", paused_reason=None)
    if not ok:
        return False

    url = _tenant_webhook_url(bot_id, row["secret"])
    tenant_bot = Bot(token=row["bot_token"])
    try:
        await tenant_bot.set_webhook(
            url,
            drop_pending_updates=False,
            allowed_updates=["message", "callback_query"],
        )
    finally:
        await tenant_bot.session.close()

    return True


async def delete_bot(user_id: int, bot_id: str) -> bool:
    row = await TenantRepo.get_token_secret_for_owner(user_id, bot_id)
    if not row:
        return False

    # 1) soft delete
    ok = await TenantRepo.soft_delete(user_id, bot_id)
    if not ok:
        return False

    # 2) rotate secret (щоб старі tenant URL точно померли)
    await TenantRepo.rotate_secret(user_id, bot_id)

    # 3) знімаємо webhook
    tenant_bot = Bot(token=row["bot_token"])
    try:
        await tenant_bot.delete_webhook(drop_pending_updates=True)
    finally:
        await tenant_bot.session.close()

    return True


# ======================================================================
# Marketplace (модулі)
# ======================================================================

# Поки що каталог хардкодом.
# Потім підтягнемо автоматом з modules/*/manifest.py.
MODULE_CATALOG: dict[str, dict[str, Any]] = {
    "core": {
        "title": "🧠 Core",
        "desc": "Базові команди /start та системні штуки",
        "price_month": 0,
    },
    "shop": {
        "title": "🛒 Shop",
        "desc": "Магазин: товари/замовлення (MVP)",
        "price_month": 100,
    },
}


async def list_bot_modules(user_id: int, bot_id: str) -> dict | None:
    # перевіряємо доступ (власник)
    row = await TenantRepo.get_token_secret_for_owner(user_id, bot_id)
    if not row:
        return None

    current = await ModuleRepo.list_all(bot_id)
    enabled = {x["module_key"] for x in current if x["enabled"]}

    modules: list[dict[str, Any]] = []
    for key, meta in MODULE_CATALOG.items():
        modules.append(
            {
                "key": key,
                "title": meta["title"],
                "desc": meta["desc"],
                "price_month": meta["price_month"],
                "enabled": key in enabled,
            }
        )

    return {"bot_id": bot_id, "status": row.get("status"), "modules": modules}


async def enable_module(user_id: int, bot_id: str, module_key: str) -> bool:
    if module_key not in MODULE_CATALOG:
        return False

    row = await TenantRepo.get_token_secret_for_owner(user_id, bot_id)
    if not row:
        return False

    # якщо бот видалений — нічого не робимо
    if (row.get("status") or "").lower() == "deleted":
        return False

    await ModuleRepo.enable(bot_id, module_key)
    return True


async def disable_module(user_id: int, bot_id: str, module_key: str) -> bool:
    if module_key not in MODULE_CATALOG:
        return False

    row = await TenantRepo.get_token_secret_for_owner(user_id, bot_id)
    if not row:
        return False

    # core краще не вимикати, щоб не "вбити" /start у tenant-бота
    if module_key == "core":
        return False

    await ModuleRepo.disable(bot_id, module_key)
    return True


# ======================================================================
# Cabinet
# ======================================================================

async def get_cabinet(user_id: int) -> dict[str, Any]:
    """
    Повертає дані для Кабінету:
    {
      "now": 123,
      "bots": [
         {
           "id": "...",
           "name": "Bot",
           "status": "active|paused|deleted",
           "plan_key": "free|basic|...",
           "paid_until_ts": 0|int,
           "paused_reason": "manual|billing|...",
           "expired": bool
         }, ...
      ]
    }
    """
    now = int(time.time())
    items = await TenantRepo.list_by_owner(user_id)

    bots: list[dict[str, Any]] = []
    for it in items:
        plan = (it.get("plan_key") or "free")
        paid_until = int(it.get("paid_until_ts") or 0)

        expired = bool(paid_until and paid_until < now)

        bots.append(
            {
                "id": it["id"],
                "name": it.get("name") or "Bot",
                "status": (it.get("status") or "active"),
                "plan_key": plan,
                "paid_until_ts": paid_until,
                "paused_reason": it.get("paused_reason"),
                "expired": expired,
            }
        )

    return {"now": now, "bots": bots}


async def create_payment_link(user_id: int, bot_id: str, months: int = 1) -> dict | None:
    """
    MVP-заглушка: повертає посилання на оплату.
    Потім тут буде інтеграція LiqPay/WayForPay/Mono і запис invoice в БД.
    """
    row = await TenantRepo.get_token_secret_for_owner(user_id, bot_id)
    if not row:
        return None

    # приклад: 100 грн/міс
    amount_uah = 100 * months
    return {
        "bot_id": bot_id,
        "months": months,
        "amount_uah": amount_uah,
        "pay_url": f"https://example.com/pay?bot_id={bot_id}&m={months}&a={amount_uah}",
        "created_ts": int(time.time()),
    }