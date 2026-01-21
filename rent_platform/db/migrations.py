from __future__ import annotations

import logging
from rent_platform.db.session import db_execute

log = logging.getLogger(__name__)

REFERRAL_DDL = [
    # --- referral core
    """
    CREATE TABLE IF NOT EXISTS ref_users (
        user_id BIGINT PRIMARY KEY,
        referrer_id BIGINT NOT NULL,
        created_ts INTEGER NOT NULL
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_ref_users_referrer
        ON ref_users(referrer_id);
    """,

    # --- balances
    """
    CREATE TABLE IF NOT EXISTS ref_balances (
        referrer_id BIGINT PRIMARY KEY,
        available_kop BIGINT NOT NULL DEFAULT 0,
        total_earned_kop BIGINT NOT NULL DEFAULT 0,
        total_paid_kop BIGINT NOT NULL DEFAULT 0,
        updated_ts INTEGER NOT NULL
    );
    """,

    # --- ledger
    """
    CREATE TABLE IF NOT EXISTS ref_ledger (
        id BIGSERIAL PRIMARY KEY,
        referrer_id BIGINT NOT NULL,
        user_id BIGINT,
        kind TEXT NOT NULL,
        amount_kop BIGINT NOT NULL,
        title TEXT,
        details TEXT,
        created_ts INTEGER NOT NULL
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_ref_ledger_referrer
        ON ref_ledger(referrer_id);
    """,

    # --- idempotency (anti-duplicate)
    """
    CREATE TABLE IF NOT EXISTS ref_applied_events (
        event_key TEXT PRIMARY KEY,
        created_ts INTEGER NOT NULL
    );
    """,

    # --- payout requests
    """
    CREATE TABLE IF NOT EXISTS ref_payout_requests (
        id BIGSERIAL PRIMARY KEY,
        referrer_id BIGINT NOT NULL,
        amount_kop BIGINT NOT NULL,
        status TEXT NOT NULL,
        note TEXT,
        created_ts INTEGER NOT NULL
    );
    """,

    # --- platform settings add column for JSON settings
    """
    ALTER TABLE platform_settings
    ADD COLUMN IF NOT EXISTS ref_json TEXT;
    """,
]


async def run_migrations() -> None:
    # важливо: кожен запит окремо (db_execute зазвичай не любить "багато SQL в одному")
    for q in REFERRAL_DDL:
        qq = (q or "").strip()
        if not qq:
            continue
        try:
            await db_execute(qq, {})
        except Exception as e:
            log.exception("Migration failed for query: %s | err=%s", qq[:80], e)
            # якщо хочеш, щоб сервіс падав при проблемі міграції — зроби: raise
            raise