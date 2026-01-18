# rent_platform/platform/storage.py
from __future__ import annotations

import time
from typing import Any

from aiogram import Bot

from rent_platform.config import settings
from rent_platform.db.repo import (
    TenantRepo,
    ModuleRepo,
    TenantSecretRepo,
    TenantIntegrationRepo,
)


def _tenant_webhook_url(tenant_id: str, secret: str) -> str:
    base = settings.WEBHOOK_URL.rstrip("/")
    prefix = settings.TENANT_WEBHOOK_PREFIX.rstrip("/")
    return f"{base}{prefix}/{tenant_id}/{secret}"


def _mask(v: str | None) -> str:
    if not v:
        return "—"
    v = str(v)
    if len(v) <= 6:
        return "***"
    return f"{v[:3]}***{v[-3:]}"


# ======================================================================
# My bots
# ======================================================================

async def list_bots(user_id: int) -> list[dict]:
    return await TenantRepo.list_by_owner(user_id)


async def add_bot(user_id: int, token: str, name: str = "Bot") -> dict:
    tenant = await TenantRepo.create(owner_user_id=user_id, bot_token=token)
    await TenantRepo.set_display_name(user_id, tenant["id"], name)

    await ModuleRepo.ensure_defaults(tenant["id"])

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

    ok = await TenantRepo.set_status(user_id, bot_id, "paused", paused_reason="manual")
    if not ok:
        return False

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

    ok = await TenantRepo.soft_delete(user_id, bot_id)
    if not ok:
        return False

    await TenantRepo.rotate_secret(user_id, bot_id)

    tenant_bot = Bot(token=row["bot_token"])
    try:
        await tenant_bot.delete_webhook(drop_pending_updates=True)
    finally:
        await tenant_bot.session.close()

    return True


# ======================================================================
# Marketplace (продукти)
# ======================================================================

# Манекен-продукт (перший “товар” в маркетплейсі)
PRODUCT_CATALOG: dict[str, dict[str, Any]] = {
    "shop_bot": {
        "title": "🛒 Luna Shop Bot",
        "short": "Магазин-бот: товари, кошик, замовлення (MVP)",
        "desc": (
            "🛒 *Luna Shop Bot*\n\n"
            "Це готовий бот-магазин, який ти береш в оренду і налаштовуєш під себе.\n\n"
            "*Що вміє (MVP):*\n"
            "• Каталог / категорії / товари\n"
            "• Кошик + оформлення\n"
            "• Замовлення + статуси\n\n"
            "*Оплати (режим 2):*\n"
            "Ти додаєш свої ключі Mono/Privat/CryptoBot — гроші йдуть тобі.\n\n"
            "_Критичні ключі платформи сховані._"
        ),
        # тариф для списання з балансу (поки просто число, далі прив’яжемо до billing)
        "rate_per_min_uah": 0.02,  # 2 коп/хв як приклад
    },
}

async def list_marketplace_products() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for key, meta in PRODUCT_CATALOG.items():
        items.append(
            {
                "key": key,
                "title": meta["title"],
                "short": meta["short"],
                "rate_per_min_uah": meta.get("rate_per_min_uah", 0),
            }
        )
    return items

async def get_marketplace_product(product_key: str) -> dict[str, Any] | None:
    meta = PRODUCT_CATALOG.get(product_key)
    if not meta:
        return None
    return {
        "key": product_key,
        "title": meta["title"],
        "desc": meta["desc"],
        "rate_per_min_uah": meta.get("rate_per_min_uah", 0),
    }

async def buy_product(user_id: int, product_key: str) -> dict[str, Any] | None:
    """
    BUY (режим 2): поки НЕ створюємо tenant, бо нам потрібен реальний BotFather token.
    Повертаємо мету продукту — а створення tenant робимо в handler flow після введення токена.
    """
    meta = PRODUCT_CATALOG.get(product_key)
    if not meta:
        return None

    return {
        "product_key": product_key,
        "title": meta["title"],
        "desc": meta["desc"],
        "rate_per_min_uah": meta.get("rate_per_min_uah", 0),
    }

# ======================================================================
# Cabinet
# ======================================================================

async def get_cabinet(user_id: int) -> dict[str, Any]:
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
    row = await TenantRepo.get_token_secret_for_owner(user_id, bot_id)
    if not row:
        return None

    amount_uah = 100 * months
    return {
        "bot_id": bot_id,
        "months": months,
        "amount_uah": amount_uah,
        "pay_url": f"https://example.com/pay?bot_id={bot_id}&m={months}&a={amount_uah}",
        "created_ts": int(time.time()),
    }


# ======================================================================
# Tenant config (режим 2): інтеграції + секрети (ключі клієнта)
# ======================================================================

SUPPORTED_PROVIDERS: dict[str, dict[str, Any]] = {
    "mono": {
        "title": "🏦 Mono",
        "secrets": [
            ("mono.token", "Mono API token"),
        ],
    },
    "privat": {
        "title": "🏦 Privat",
        "secrets": [
            ("privat.token", "Privat API token"),
        ],
    },
    "cryptobot": {
        "title": "🪙 CryptoBot",
        "secrets": [
            ("cryptobot.token", "CryptoBot token"),
        ],
    },
}


async def get_bot_config(user_id: int, bot_id: str) -> dict | None:
    row = await TenantRepo.get_token_secret_for_owner(user_id, bot_id)
    if not row:
        return None
    if (row.get("status") or "").lower() == "deleted":
        return None

    # інтеграції
    ints = await TenantIntegrationRepo.list_all(bot_id)
    enabled_map = {x["provider"]: bool(x["enabled"]) for x in ints}

    providers: list[dict[str, Any]] = []
    for p, meta in SUPPORTED_PROVIDERS.items():
        providers.append(
            {
                "provider": p,
                "title": meta["title"],
                "enabled": bool(enabled_map.get(p, False)),
                "secrets": [
                    {
                        "key": sk,
                        "label": lbl,
                        "value_masked": _mask((await TenantSecretRepo.get(bot_id, sk) or {}).get("secret_value")),
                    }
                    for sk, lbl in meta["secrets"]
                ],
            }
        )

    return {"bot_id": bot_id, "status": row.get("status"), "providers": providers}


async def toggle_integration(user_id: int, bot_id: str, provider: str) -> bool:
    if provider not in SUPPORTED_PROVIDERS:
        return False
    row = await TenantRepo.get_token_secret_for_owner(user_id, bot_id)
    if not row:
        return False
    if (row.get("status") or "").lower() == "deleted":
        return False

    cur = await TenantIntegrationRepo.get(bot_id, provider)
    new_enabled = not bool(cur.get("enabled")) if cur else True
    await TenantIntegrationRepo.set_enabled(bot_id, provider, new_enabled)
    return True


async def set_bot_secret(user_id: int, bot_id: str, secret_key: str, secret_value: str) -> bool:
    # секрет має бути з нашого whitelist
    allowed = set()
    for meta in SUPPORTED_PROVIDERS.values():
        for sk, _lbl in meta["secrets"]:
            allowed.add(sk)
    if secret_key not in allowed:
        return False

    row = await TenantRepo.get_token_secret_for_owner(user_id, bot_id)
    if not row:
        return False
    if (row.get("status") or "").lower() == "deleted":
        return False

    await TenantSecretRepo.upsert(bot_id, secret_key, secret_value.strip())
    return True