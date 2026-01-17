# rent_platform/main.py

import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from rent_platform.config import settings
from rent_platform.core.webhook import handle_webhook
from rent_platform.platform.handlers.start import router as platform_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Rent Platform",
    description="Multi-tenant Telegram Bot Platform",
    version="0.1.0"
)

# --- health check ---
@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "rent-platform",
        "message": "🚀 Platform is alive"
    }

# --- telegram webhook ---
@app.post("/webhook/{tenant_id}")
async def telegram_webhook(tenant_id: str, request: Request):
    payload = await request.json()
    try:
        await handle_webhook(tenant_id, payload)
        return JSONResponse({"ok": True})
    except Exception as e:
        logger.exception("Webhook error")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

# --- platform (main bot) routes ---
app.include_router(platform_router, prefix="/platform")

logger.info("🚀 Rent Platform started")