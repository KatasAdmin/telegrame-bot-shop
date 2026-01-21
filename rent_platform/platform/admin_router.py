from __future__ import annotations

import time
from fastapi import APIRouter, Header, HTTPException

from rent_platform.config import settings
from rent_platform.db.repo import PlatformSettingsRepo

router = APIRouter(prefix="/admin", tags=["admin"])


def _check(x_admin_token: str | None) -> None:
    if not x_admin_token or x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/platform-settings")
async def get_platform_settings(x_admin_token: str | None = Header(default=None)):
    _check(x_admin_token)
    row = await PlatformSettingsRepo.get()
    return row or {"cabinet_banner_url": "", "updated_ts": 0}


@router.post("/cabinet-banner")
async def set_cabinet_banner(payload: dict, x_admin_token: str | None = Header(default=None)):
    _check(x_admin_token)
    url = str(payload.get("url") or "").strip()
    await PlatformSettingsRepo.upsert_cabinet_banner(url)
    return {"ok": True, "cabinet_banner_url": url, "updated_ts": int(time.time())}