from __future__ import annotations

import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = os.environ["DATABASE_URL"]

# Railway зазвичай дає postgresql://, але async драйвер хоче +asyncpg
if DATABASE_URL.startswith("postgresql://"):
    ASYNC_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    ASYNC_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
else:
    ASYNC_URL = DATABASE_URL

engine = create_async_engine(ASYNC_URL, pool_pre_ping=True)


async def db_fetch_one(query: str, params: dict) -> dict | None:
    async with engine.connect() as conn:
        res = await conn.execute(text(query), params)
        row = res.mappings().first()
        return dict(row) if row else None


async def db_fetch_all(query: str, params: dict) -> list[dict]:
    async with engine.connect() as conn:
        res = await conn.execute(text(query), params)
        return [dict(r) for r in res.mappings().all()]