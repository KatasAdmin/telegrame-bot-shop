from __future__ import annotations

import logging
import time
from typing import Any

from aiogram import Bot

from rent_platform.config import settings
from rent_platform.db.repo import (
    TenantRepo,
    ModuleRepo,
    TenantSecretRepo,
    TenantIntegrationRepo,
    AccountRepo,
    LedgerRepo,
    InvoiceRepo,
)
from rent_platform.products.catalog import PRODUCT_CATALOG

log = logging.getLogger(__name__)


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


def _uah_to_kop(amount_uah: int) -> int:
    return max(0, int(amount_uah) * 100)


# ======================================================================
# My bots
# ======================================================================

async def list_bots(user_id: int) -> list[dict]:
    return await TenantRepo.list_by_owner(user_id)


async def add_bot(user_id: int, token: str, name: str = "Bot", product_key: str | None = None) -> dict:
    tenant = await TenantRepo.create(owner_user_id=user_id, bot_token=token)

    await TenantRepo.set_display_name(user_id, tenant["id"], name)

    await ModuleRepo.enable(tenant["id"], "core")

    if product_key:
        await TenantRepo.set_product_key(user_id, tenant["id"], product_key)
        await ModuleRepo.enable(tenant["id"], product_key)
    else:
        await ModuleRepo.enable(tenant["id"], "shop")

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

    return {"id": tenant["id"], "name": name, "status": tenant["status"], "product_key": product_key}


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

    await AccountRepo.ensure(user_id)
    acc = await AccountRepo.get(user_id)
    balance_kop = int((acc or {}).get("balance_kop") or 0)

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
                "product_key": it.get("product_key"),
                "expired": expired,
            }
        )

    ledger = await LedgerRepo.list_last(user_id, limit=10)
    return {"now": now, "balance_kop": balance_kop, "bots": bots, "ledger": ledger}}


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
# TopUp (баланс)
# ======================================================================

async def create_topup_invoice(user_id: int, amount_uah: int, provider: str) -> dict | None:
    amount_uah = int(amount_uah)
    if amount_uah < 10:
        return None
    if provider not in ("mono", "privat", "cryptobot"):
        return None

    amount_kop = _uah_to_kop(amount_uah)
    pay_url = f"https://example.com/topup?u={user_id}&a={amount_uah}&p={provider}"

    inv = await InvoiceRepo.create(
        owner_user_id=user_id,
        provider=provider,
        amount_kop=amount_kop,
        pay_url=pay_url,
        meta={"amount_uah": amount_uah, "provider": provider},
    )

    log.info("TOPUP invoice created: uid=%s inv=%s", user_id, inv)

    if not inv or not inv.get("id"):
        return None

    return {
        "invoice_id": int(inv["id"]),
        "provider": provider,
        "amount_uah": amount_uah,
        "amount_kop": amount_kop,
        "pay_url": pay_url,
        "created_ts": int(inv.get("created_ts") or 0),
    }


async def confirm_topup_paid_test(user_id: int, invoice_id: int) -> dict | None:
    inv = await InvoiceRepo.get_for_owner(user_id, int(invoice_id))
    log.info("TOPUP confirm requested: uid=%s invoice_id=%s inv=%s", user_id, invoice_id, inv)

    if not inv:
        return None

    status = (inv.get("status") or "").lower()
    if status != "pending":
    return {"already": True, "status": status}

    amount_kop = int(inv.get("amount_kop") or 0)
    if amount_kop <= 0:
        return None

# 0) if already credited -> idempotent exit
    if await LedgerRepo.has_topup_invoice(user_id, int(invoice_id)):
# інвойс могли вже провести раніше
        await AccountRepo.ensure(user_id)
        acc = await AccountRepo.get(user_id)
        bal = int((acc or {}).get("balance_kop") or 0)
        return {"already": True, "status": "credited", "new_balance_kop": bal}

# 1) mark paid
    await InvoiceRepo.mark_paid(user_id, int(invoice_id))

# 2) balance +
    await AccountRepo.ensure(user_id)
    acc = await AccountRepo.get(user_id)
    balance = int((acc or {}).get("balance_kop") or 0) + amount_kop
    await AccountRepo.set_balance(user_id, balance)

# 3) ledger +
    await LedgerRepo.add(
        user_id,
        "topup",
        +amount_kop,
        tenant_id=None,
        meta={"invoice_id": int(invoice_id), "provider": inv.get("provider")},
    )

    return {"ok": True, "new_balance_kop": balance, "amount_kop": amount_kop}
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