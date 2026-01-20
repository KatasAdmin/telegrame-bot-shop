from __future__ import annotations

import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = os.environ["DATABASE_URL"]

if DATABASE_URL.startswith("postgresql://"):
    ASYNC_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    ASYNC_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
else:
    ASYNC_URL = DATABASE_URL

engine = create_async_engine(ASYNC_URL, pool_pre_ping=True)


async def db_fetch_one(query: str, params: dict | None = None) -> dict | None:
    params = params or {}
    # ВАЖЛИВО: begin() => commit/rollback автоматом, і INSERT ... RETURNING стане "реальним"
    async with engine.begin() as conn:
        res = await conn.execute(text(query), params)
        row = res.mappings().first()
        return dict(row) if row else None


async def db_fetch_all(query: str, params: dict | None = None) -> list[dict]:
    params = params or {}
    async with engine.begin() as conn:
        res = await conn.execute(text(query), params)
        return [dict(r) for r in res.mappings().all()]


async def db_execute(query: str, params: dict | None = None) -> int:
    params = params or {}
    async with engine.begin() as conn:
        res = await conn.execute(text(query), params)
        return int(getattr(res, "rowcount", 0) or 0)