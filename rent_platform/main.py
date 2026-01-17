# rent_platform/main.py
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, HTTPException
from aiogram import Bot, Dispatcher
from aiogram.types import Update

from rent_platform.config import settings
from rent_platform.core.tenant_ctx import init_tenants, get_tenant, set_current_tenant
from rent_platform.core.modules import init_modules
from rent_platform.core.webhook import handle_webhook as handle_tenant_webhook
from rent_platform.platform.handlers.start import router as start_router

log = logging.getLogger(__name__)

app = FastAPI()

# platform bot
bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()
dp.include_router(start_router)

_webhook_inited = False  # локальний флаг (на воркер)


@app.on_event("startup")
async def on_startup():
    global _webhook_inited
    logging.basicConfig(level=logging.INFO)

    init_tenants()
    init_modules()

    webhook_full = settings.WEBHOOK_URL.rstrip("/") + settings.WEBHOOK_PATH

    if _webhook_inited:
        log.info("Startup: webhook already inited in this worker")
        return

    try:
        info = await bot.get_webhook_info()
        if (info.url or "").strip() == webhook_full:
            log.info("Webhook already correct: %s", webhook_full)
            _webhook_inited = True
            return
    except Exception as e:
        log.warning("getWebhookInfo failed: %s", e)

    await bot.set_webhook(
        webhook_full,
        drop_pending_updates=False,
        allowed_updates=["message", "callback_query"],
    )
    _webhook_inited = True
    log.info("Webhook set to %s", webhook_full)


@app.on_event("shutdown")
async def on_shutdown():
    await bot.session.close()


@app.get("/")
async def root():
    return {"ok": True, "service": "rent_platform"}


# ✅ Platform bot webhook (aiogram dp)
@app.post(settings.WEBHOOK_PATH)
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


# ✅ Tenant bots webhook (module router)
@app.post(f"{settings.TENANT_WEBHOOK_PREFIX}" + "/{bot_id}/{secret}")
async def tenant_webhook(bot_id: str, secret: str, req: Request):
    tenant = get_tenant(bot_id)
    if not tenant or tenant.secret != secret:
        raise HTTPException(status_code=404, detail="unknown tenant")

    update: dict[str, Any] = await req.json()

    # контекст на час обробки
    set_current_tenant(tenant)
    await handle_tenant_webhook(tenant, update)

    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("rent_platform.main:app", host="0.0.0.0", port=int(settings.PORT))