import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from rent_platform.config import settings
from rent_platform.core.tenant_ctx import (
    register_tenant,
    init_tenants,
)
from rent_platform.core.webhook import set_webhook


# -------------------------
# LOGGING
# -------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# -------------------------
# APP FACTORY
# -------------------------
async def create_app() -> web.Application:
    """
    Створює aiohttp app + ініціалізує всі tenant-и
    """
    app = web.Application()

    # ---- Dispatcher (один на всі tenant-и)
    dp = Dispatcher()
    app["dp"] = dp

    # ---- Реєстрація tenant-ів (ПОКИ ХАРДКОД)
    register_tenant(
        tenant_id="demo",
        bot_token=settings.BOT_TOKEN,
        modules=["shop"],
    )

    # ---- Ініціалізація tenant-ів (створює Bot, підключає роутери)
    await init_tenants(dp)

    # ---- Webhook handler
    SimpleRequestHandler(
        dispatcher=dp,
        bot=None,  # боти беруться з tenant_ctx
    ).register(app, path="/webhook")

    setup_application(app, dp, bot=None)

    logger.info("🚀 Platform initialized")
    return app


# -------------------------
# START
# -------------------------
async def main():
    logger.info("🚀 Starting Rent Platform...")

    app = await create_app()

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(
        runner,
        host="0.0.0.0",
        port=settings.PORT,
    )

    await site.start()

    # ---- Webhook (один URL, мульти-tenant всередині)
    await set_webhook(settings.WEBHOOK_URL)

    logger.info(f"✅ Server started on port {settings.PORT}")

    # ---- Keep alive
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())