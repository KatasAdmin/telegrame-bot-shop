# rent_platform/main.py
from __future__ import annotations

import time
import logging
from fastapi import FastAPI, Request, HTTPException
from aiogram import Bot, Dispatcher
from aiogram.types import Update

from rent_platform.config import settings
from rent_platform.core.modules import init_modules
from rent_platform.core.tenant_ctx import init_tenants
from rent_platform.db.repo import TenantRepo, ModuleRepo
from rent_platform.core.registry import get_module

log = logging.getLogger(__name__)

app = FastAPI()

# Platform bot (керує SaaS-меню)
platform_bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()

from rent_platform.platform.handlers.start import router as start_router
dp.include_router(start_router)

_webhook_inited = False

# ✅ кеш tenant Bot-ів (на процес)
_TENANT_BOTS: dict[str, Bot] = {}


def _get_tenant_bot(tenant_id: str, token: str) -> Bot:
    bot = _TENANT_BOTS.get(tenant_id)
    if bot:
        return bot
    bot = Bot(token=token)
    _TENANT_BOTS[tenant_id] = bot
    return bot


@app.on_event("startup")
async def on_startup():
    global _webhook_inited
    logging.basicConfig(level=logging.INFO)

    init_tenants()
    init_modules()
    log.info("Tenant prefix: %s", settings.TENANT_WEBHOOK_PREFIX)

    webhook_full = settings.WEBHOOK_URL.rstrip("/") + settings.WEBHOOK_PATH

    if _webhook_inited:
        log.info("Startup: webhook already inited in this worker")
        return

    try:
        info = await platform_bot.get_webhook_info()
        if (info.url or "").strip() == webhook_full:
            log.info("Webhook already correct: %s", webhook_full)
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
    await platform_bot.session.close()

    for bot in _TENANT_BOTS.values():
        try:
            await bot.session.close()
        except Exception:
            pass
    _TENANT_BOTS.clear()

    try:
        from rent_platform.db.session import engine
        await engine.dispose()
    except Exception:
        pass


@app.get("/")
async def root():
    return {"ok": True, "service": "rent_platform"}


# ===== Platform webhook =====
@app.post(settings.WEBHOOK_PATH)
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.model_validate(data)
    await dp.feed_update(platform_bot, update)
    return {"ok": True}


# ===== Tenant webhook =====
@app.post(f"{settings.TENANT_WEBHOOK_PREFIX}" + "/{bot_id}/{secret}")
async def tenant_webhook(bot_id: str, secret: str, req: Request):
    data = await req.json()

    tenant = await TenantRepo.get_by_id(bot_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="tenant not found")

    if tenant["secret"] != secret:
        raise HTTPException(status_code=403, detail="bad secret")

    st = (tenant.get("status") or "active").lower()

    # deleted/paused — не приймаємо апдейти взагалі
    if st == "deleted":
        raise HTTPException(status_code=410, detail="tenant deleted")
    if st == "paused":
        # 200 щоб Telegram не ретраїв, але модулі не викликаємо
        return {"ok": True}

    # ===== billing gate (MVP) =====
    now = int(time.time())
    plan = (tenant.get("plan_key") or "free").lower()
    paid_until = int(tenant.get("paid_until_ts") or 0)

    # якщо платний план і дата оплати задана — перевіряємо прострочку
    if plan != "free" and paid_until and paid_until < now:
        # авто-пауза
        try:
            await TenantRepo.set_status(
                owner_user_id=int(tenant["owner_user_id"]),
                tenant_id=bot_id,
                status="paused",
                paused_reason="billing",
            )
        except Exception:
            pass
        return {"ok": True}

    tenant_bot = _get_tenant_bot(bot_id, tenant["bot_token"])

    enabled = await ModuleRepo.list_enabled(bot_id)
    for module_key in enabled:
        handler = get_module(module_key)
        if not handler:
            continue
        handled = await handler(tenant, data, tenant_bot)
        if handled:
            break

    return {"ok": True}