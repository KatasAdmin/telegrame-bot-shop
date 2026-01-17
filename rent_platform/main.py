# rent_platform/main.py
from __future__ import annotations

import logging
import os

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher
from aiogram.types import Update

from rent_platform.config import settings
from rent_platform.core.tenant_ctx import init_tenants
from rent_platform.platform.handlers.start import router as start_router

log = logging.getLogger(__name__)

app = FastAPI()

bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()
dp.include_router(start_router)

_webhook_inited = False  # ✅ локальний флаг (на воркер)


@app.on_event("startup")
async def on_startup():
    global _webhook_inited
    logging.basicConfig(level=logging.INFO)

    init_tenants()

    webhook_full = settings.WEBHOOK_URL.rstrip("/") + settings.WEBHOOK_PATH

    # ✅ ставимо тільки якщо ще не ставили у цьому воркері
    if _webhook_inited:
        log.info("Startup: webhook already inited in this worker")
        return

    # ✅ і додатково: якщо Telegram вже має правильний webhook — не чіпаємо
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
        drop_pending_updates=False,  # ✅ не губимо апдейти під час деву
        allowed_updates=["message", "callback_query"],
    )
    _webhook_inited = True
    log.info("Webhook set to %s", webhook_full)


@app.on_event("shutdown")
async def on_shutdown():
    # ❗️на проді краще НЕ delete_webhook, бо при рестартах буде "вікно тиші"
    # await bot.delete_webhook(drop_pending_updates=True)
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("rent_platform.main:app", host="0.0.0.0", port=int(settings.PORT))