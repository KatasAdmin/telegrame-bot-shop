from __future__ import annotations

import logging
from rent_platform.db.session import db_execute

log = logging.getLogger(__name__)

DDL: list[str] = [
    # =========================================================
    # 0) platform_settings (MUST exist before any ALTER/Repo use)
    # =========================================================
    """
    CREATE TABLE IF NOT EXISTS platform_settings (
        id INTEGER PRIMARY KEY,
        cabinet_banner_url TEXT NOT NULL DEFAULT '',
        ref_json TEXT NOT NULL DEFAULT '',
        updated_ts INTEGER NOT NULL DEFAULT 0
    );
    """,
    # ensure singleton row id=1
    """
    INSERT INTO platform_settings (id, cabinet_banner_url, ref_json, updated_ts)
    VALUES (1, '', '', 0)
    ON CONFLICT (id) DO NOTHING;
    """,

    # =========================================================
    # 1) referral core
    # =========================================================
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

    # =========================================================
    # 2) referral balances
    # =========================================================
    """
    CREATE TABLE IF NOT EXISTS ref_balances (
        referrer_id BIGINT PRIMARY KEY,
        available_kop BIGINT NOT NULL DEFAULT 0,
        total_earned_kop BIGINT NOT NULL DEFAULT 0,
        total_paid_kop BIGINT NOT NULL DEFAULT 0,
        updated_ts INTEGER NOT NULL DEFAULT 0
    );
    """,

    # =========================================================
    # 3) referral ledger
    # =========================================================
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

    # =========================================================
    # 4) idempotency (anti-duplicate)
    # =========================================================
    """
    CREATE TABLE IF NOT EXISTS ref_applied_events (
        event_key TEXT PRIMARY KEY,
        created_ts INTEGER NOT NULL
    );
    """,

    # =========================================================
    # 5) payout requests
    # =========================================================
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
    """
    CREATE INDEX IF NOT EXISTS idx_ref_payout_requests_referrer
        ON ref_payout_requests(referrer_id);
    """,
]


async def run_migrations() -> None:
    # важливо: кожен запит окремо (db_execute зазвичай не любить "багато SQL в одному")
    for q in DDL:
        qq = (q or "").strip()
        if not qq:
            continue
        try:
            await db_execute(qq, {})
        except Exception as e:
            log.exception("Migration failed for query: %s | err=%s", qq[:120], e)
            raise