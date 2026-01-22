# rent_platform/main.py
from __future__ import annotations

import asyncio
import logging
import time

from fastapi import FastAPI, Request, HTTPException
from aiogram import Bot, Dispatcher
from aiogram.types import Update

from rent_platform.config import settings
from rent_platform.core.modules import init_modules
from rent_platform.core.tenant_ctx import init_tenants
from rent_platform.core.registry import get_module
from rent_platform.db.repo import TenantRepo, ModuleRepo
from rent_platform.db.migrations import run_migrations
from rent_platform.db.session import db_execute  # ✅ напряму в БД (без owner_user_id)

from rent_platform.core.billing import billing_daemon_daily_midnight, billing_loop
from rent_platform.platform.admin_router import router as admin_router  # FastAPI router

log = logging.getLogger(__name__)

app = FastAPI()
app.include_router(admin_router)

# =========================================================
# Platform bot + dispatcher
# =========================================================
platform_bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()

# ✅ Aiogram routers (ВАЖЛИВО: імпорт ПІСЛЯ dp)
from rent_platform.platform.handlers.admin_panel import router as admin_panel_router  # noqa: E402
from rent_platform.platform.handlers.admin_ref import router as admin_ref_router  # noqa: E402
from rent_platform.platform.handlers.start import router as start_router  # noqa: E402

dp.include_router(admin_panel_router)
dp.include_router(admin_ref_router)
dp.include_router(start_router)

_webhook_inited = False

# ✅ кеш tenant Bot-ів (на процес)
_TENANT_BOTS: dict[str, Bot] = {}

_BILL_STOP = asyncio.Event()
_BILL_TASK: asyncio.Task | None = None
_DAILY_TASK: asyncio.Task | None = None


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
    blocked=True: tenant webhook не обробляємо (віддаємо 200 OK).
    ВАЖЛИВО: тут НЕ робимо auto-resume для billing pause.
    Auto-resume робиться після поповнення балансу/оплати.
    """
    st = (tenant.get("status") or "active").lower()
    pr = (tenant.get("paused_reason") or "").lower()

    if st == "deleted":
        return True, "deleted"

    if st == "paused":
        return True, pr or "paused"

    # legacy: якщо paid_until_ts ще використовується
    now = int(time.time())
    paid_until = int(tenant.get("paid_until_ts") or 0)
    expired = paid_until > 0 and paid_until <= now
    if expired:
        await _system_set_status(tenant["id"], "paused", "billing")
        tenant["status"] = "paused"
        tenant["paused_reason"] = "billing"
        return True, "billing"

    return False, None

    # якщо баланс/оплата знову ок — авто-resume після billing pause
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
    global _BILL_TASK, _DAILY_TASK, _webhook_inited

    # ✅ міграції
    await run_migrations()

    # ✅ ініт
    init_tenants()
    init_modules()

    # ✅ Daily billing daemon (00:00)
    if _DAILY_TASK is None:
        _DAILY_TASK = asyncio.create_task(billing_daemon_daily_midnight(platform_bot, _BILL_STOP))
        log.info("billing daily daemon started")

    webhook_full = settings.WEBHOOK_URL.rstrip("/") + settings.WEBHOOK_PATH
    log.info("Platform webhook target: %s", webhook_full)
    log.info("Tenant prefix: %s", settings.TENANT_WEBHOOK_PREFIX)

    if _webhook_inited:
        if _BILL_TASK is None:
            _BILL_TASK = asyncio.create_task(billing_loop(platform_bot, _BILL_STOP))
            log.info("billing loop started")
        return

    try:
        info = await platform_bot.get_webhook_info()
        if (info.url or "").strip() == webhook_full:
            log.info("Webhook already correct: %s", webhook_full)
            _webhook_inited = True

            if _BILL_TASK is None:
                _BILL_TASK = asyncio.create_task(billing_loop(platform_bot, _BILL_STOP))
                log.info("billing loop started")
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

    if _BILL_TASK is None:
        _BILL_TASK = asyncio.create_task(billing_loop(platform_bot, _BILL_STOP))
        log.info("billing loop started")


@app.on_event("shutdown")
async def on_shutdown():
    global _BILL_TASK, _DAILY_TASK

    _BILL_STOP.set()

    if _BILL_TASK:
        try:
            await _BILL_TASK
        except Exception:
            pass
        _BILL_TASK = None

    if _DAILY_TASK:
        try:
            await _DAILY_TASK
        except Exception:
            pass
        _DAILY_TASK = None

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

    if tenant.get("secret") != secret:
        raise HTTPException(status_code=403, detail="bad secret")

    st = (tenant.get("status") or "active").lower()
    if st == "deleted":
        raise HTTPException(status_code=410, detail="tenant deleted")

    blocked, reason = await _maybe_apply_billing_pause(tenant)
    if blocked:
        return {"ok": True, "blocked": True, "reason": reason}

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