# app/main.py
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI, Request, HTTPException
from aiogram import Bot, Dispatcher
from aiogram.types import Update

from config import settings


# ---------------------------------------------------------
# Bot registry (тимчасово in-memory).
# Пізніше замінимо на DB: tenant_bots table (token, tenant_id, module_enabled ...)
# ---------------------------------------------------------

_bots: Dict[str, Bot] = {}
_dispatchers: Dict[str, Dispatcher] = {}


def _get_or_create_dp(bot_token: str) -> Dispatcher:
    if bot_token in _dispatchers:
        return _dispatchers[bot_token]

    dp = Dispatcher()

    from platform.handlers.start import router as platform_router
    dp.include_router(platform_router)

    _dispatchers[bot_token] = dp
    return dp


def _get_or_create_bot(bot_token: str) -> Bot:
    if bot_token in _bots:
        return _bots[bot_token]
    b = Bot(token=bot_token)
    _bots[bot_token] = b
    return b


# ---------------------------------------------------------
# WEBHOOK dispatcher: один endpoint, багато ботів
# Важливий момент: Telegram шле update НА КОНКРЕТНИЙ BOT webhook.
# Тому ми маємо вміти визначати, який токен обробляє цей endpoint.
#
# Найпростіше/надійно:
# - робимо webhook URL різним для кожного бота: /tg/webhook/<token_hash>
# або
# - /tg/webhook/<bot_id>
#
# Для старту зробимо: /tg/webhook/{bot_key}
# де bot_key = "platform" або "tenant_<id>" (пізніше з DB)
# ---------------------------------------------------------

def resolve_token_by_key(bot_key: str) -> str:
    # START: тільки platform бот
    if bot_key == "platform":
        if not settings.PLATFORM_BOT_TOKEN:
            raise ValueError("PLATFORM_BOT_TOKEN is empty")
        return settings.PLATFORM_BOT_TOKEN

    # LATER: tenant bots
    # приклад:
    # if bot_key.startswith("tenant_"):
    #     tenant_id = int(bot_key.split("_", 1)[1])
    #     token = await db_get_tenant_token(tenant_id)
    #     return token

    raise ValueError(f"Unknown bot_key: {bot_key}")


# ---------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # on startup
    # Ставимо webhook для platform бота (для тесту)
    if settings.WEBHOOK_BASE_URL:
        bot = _get_or_create_bot(settings.PLATFORM_BOT_TOKEN)
        url = settings.WEBHOOK_BASE_URL.rstrip("/") + settings.WEBHOOK_PATH + "/platform"

        # Можеш додати secret_token (Telegram підтримує) — але він не завжди потрібен
        await bot.set_webhook(url=url, secret_token=settings.WEBHOOK_SECRET or None)

    yield

    # on shutdown
    # (не обов’язково, але гарно)
    try:
        if settings.PLATFORM_BOT_TOKEN:
            bot = _get_or_create_bot(settings.PLATFORM_BOT_TOKEN)
            await bot.delete_webhook(drop_pending_updates=False)
    except Exception:
        pass

    for b in _bots.values():
        try:
            await b.session.close()
        except Exception:
            pass


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root():
    return {"ok": True, "service": "rent-platform"}


@app.post(settings.WEBHOOK_PATH + "/{bot_key}")
async def telegram_webhook(bot_key: str, request: Request):
    # optional: simple security via Telegram secret header (if you set it)
    if settings.WEBHOOK_SECRET:
        got = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if got != settings.WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Bad secret token")

    try:
        token = resolve_token_by_key(bot_key)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

    bot = _get_or_create_bot(token)
    dp = _get_or_create_dp(token)

    data = await request.json()
    update = Update(**data)

    # aiogram v3: feed_update
    await dp.feed_update(bot, update)
    return {"ok": True}


# Локальний запуск (не Railway)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)