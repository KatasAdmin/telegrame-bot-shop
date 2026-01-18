# rent_platform/main.py
from __future__ import annotations

import logging
import time
import asyncio

from rent_platform.core.billing import billing_loop
from fastapi import FastAPI, Request, HTTPException
from aiogram import Bot, Dispatcher
from aiogram.types import Update

from rent_platform.config import settings
from rent_platform.core.modules import init_modules
from rent_platform.core.tenant_ctx import init_tenants
from rent_platform.db.repo import TenantRepo, ModuleRepo
from rent_platform.core.registry import get_module

# ✅ напряму в БД (щоб НЕ ламати repo методами з owner_user_id)
from rent_platform.db.session import db_execute

log = logging.getLogger(__name__)

app = FastAPI()

# Platform bot (керує SaaS-меню)
platform_bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()

from rent_platform.platform.handlers.start import router as start_router  # noqa: E402

dp.include_router(start_router)

_webhook_inited = False

# ✅ кеш tenant Bot-ів (на процес)
_TENANT_BOTS: dict[str, Bot] = {}
_BILL_STOP = asyncio.Event()
_BILL_TASK: asyncio.Task | None = None

def _get_tenant_bot(tenant_id: str, token: str) -> Bot:
    bot = _TENANT_BOTS.get(tenant_id)
    if bot:
        return bot
    bot = Bot(token=token)
    _TENANT_BOTS[tenant_id] = bot
    return bot


async def _system_set_status(tenant_id: str, status: str, paused_reason: str | None) -> None:
    """
    Системне оновлення статусу без owner_user_id.
    Використовуємо тут, бо в tenant webhook нема user_id.
    """
    q = """
    UPDATE tenants
    SET status = :st, paused_reason = :pr
    WHERE id = :id
    """
    await db_execute(q, {"st": status, "pr": paused_reason, "id": tenant_id})


async def _maybe_apply_billing_pause(tenant: dict) -> tuple[bool, str | None]:
    """
    Повертає (blocked, reason_text)
    blocked=True означає: цей tenant зараз НЕ обробляємо (200 OK).
    """
    now = int(time.time())
    st = (tenant.get("status") or "active").lower()
    pr = tenant.get("paused_reason")

    # deleted — завжди блокуємо (і краще 410)
    if st == "deleted":
        return True, "deleted"

    paid_until = int(tenant.get("paid_until_ts") or 0)
    expired = paid_until > 0 and paid_until <= now

    # Якщо прострочено — авто-пауза billing (але manual не чіпаємо)
    if expired:
        # якщо вже paused billing — просто блокуємо
        if st == "paused" and pr == "billing":
            return True, "billing"

        # якщо manual paused — залишаємо як є і блокуємо
        if st == "paused" and pr == "manual":
            return True, "manual"

        # якщо active (або інше) — ставимо paused billing
        if st != "paused":
            await _system_set_status(tenant["id"], "paused", "billing")
            # локально теж оновимо, щоб нижче не було сюрпризів
            tenant["status"] = "paused"
            tenant["paused_reason"] = "billing"
        return True, "billing"

    # Якщо НЕ прострочено, але раніше було paused billing — авто-resume
    if st == "paused" and pr == "billing":
        await _system_set_status(tenant["id"], "active", None)
        tenant["status"] = "active"
        tenant["paused_reason"] = None
        return False, None

    # manual pause лишається manual pause
    if st == "paused":
        return True, pr or "paused"

    return False, None


@app.on_event("startup")
async def on_startup():
    global _webhook_inited
    logging.basicConfig(level=logging.INFO)

    init_tenants()
    init_modules()

    log.info("Префикс арендатора: %s", settings.TENANT_WEBHOOK_PREFIX)

    webhook_full = settings.WEBHOOK_URL.rstrip("/") + settings.WEBHOOK_PATH

    if _webhook_inited:
        log.info("Startup: webhook already inited in this worker")
        return

    try:
        info = await platform_bot.get_webhook_info()
        if (info.url or "").strip() == webhook_full:
            log.info("Webhook уже корректен: %s", webhook_full)
            _webhook_inited = True
            return
    except Exception as e:
        log.warning("getWebhookInfo failed: %s", e)

    await platform_bot.set_webhook(
        webhook_full,
        drop_pending_updates=False,
        allowed_updates=["message", "callback_query"],
    )
    _webhook_inited = True
    log.info("Webhook set to %s", webhook_full)


@app.on_event("shutdown")
async def on_shutdown():
    # platform bot session
    await platform_bot.session.close()

    # tenant bot sessions
    for bot in _TENANT_BOTS.values():
        try:
            await bot.session.close()
        except Exception:
            pass
    _TENANT_BOTS.clear()

    # db engine dispose (якщо є)
    try:
        from rent_platform.db.session import engine

        await engine.dispose()
    except Exception:
        pass


@app.get("/")
async def root():
    return {"ok": True, "service": "rent_platform"}


# =========================================================
# Platform webhook (керує меню платформи)
# =========================================================
@app.post(settings.WEBHOOK_PATH)
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.model_validate(data)

    try:
        await dp.feed_update(platform_bot, update)
    except Exception as e:
        # щоб Telegram не спамив ретраями — повертаємо 200
        log.exception("platform feed_update failed: %s", e)

    return {"ok": True}


# =========================================================
# Tenant webhook (апдейти орендованих ботів)
# =========================================================
@app.post(f"{settings.TENANT_WEBHOOK_PREFIX}" + "/{bot_id}/{secret}")
async def tenant_webhook(bot_id: str, secret: str, req: Request):
    data = await req.json()

    tenant = await TenantRepo.get_by_id(bot_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="tenant not found")

    # секрет — щоб старі URL помирали після rotate_secret
    if tenant.get("secret") != secret:
        raise HTTPException(status_code=403, detail="bad secret")

    # 1) deleted → 410
    st = (tenant.get("status") or "active").lower()
    if st == "deleted":
        raise HTTPException(status_code=410, detail="tenant deleted")

    # 2) Billing auto-pause / auto-resume
    blocked, reason = await _maybe_apply_billing_pause(tenant)
    if blocked:
        # paused/manual/billing — просто 200, без ретраїв
        return {"ok": True, "blocked": True, "reason": reason}

    # 3) Якщо активний — проганяємо по модулях
    tenant_bot = _get_tenant_bot(bot_id, tenant["bot_token"])

    enabled = await ModuleRepo.list_enabled(bot_id)
    for module_key in enabled:
        handler = get_module(module_key)
        if not handler:
            continue
        try:
            handled = await handler(tenant, data, tenant_bot)
        except Exception as e:
            log.exception("tenant module failed tenant=%s module=%s err=%s", bot_id, module_key, e)
            handled = False
        if handled:
            break

    return {"ok": True}