# rent_platform/main.py
from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher
from aiogram.types import Update

from rent_platform.config import settings
from rent_platform.core.tenant_ctx import init_tenants  # заглушка вже є
from rent_platform.platform.handlers.start import router as start_router

log = logging.getLogger(__name__)

app = FastAPI()

bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()
dp.include_router(start_router)


@app.on_event("startup")
async def on_startup():
    logging.basicConfig(level=logging.INFO)

    # init (пізніше: БД, tenants, registry)
    init_tenants()

    # webhook set
    webhook_full = settings.WEBHOOK_URL.rstrip("/") + settings.WEBHOOK_PATH
    await bot.set_webhook(webhook_full)
    log.info("Webhook set to %s", webhook_full)


@app.on_event("shutdown")
async def on_shutdown():
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.session.close()


@app.get("/")
async def root():
    return {"ok": True, "service": "rent_platform"}


@app.post(settings.WEBHOOK_PATH)
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


# optional local run (не заважає Railway)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("rent_platform.main:app", host="0.0.0.0", port=int(settings.PORT))