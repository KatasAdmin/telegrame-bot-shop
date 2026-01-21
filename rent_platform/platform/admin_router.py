from __future__ import annotations

import json
import time
from typing import Any

from fastapi import APIRouter, Header, HTTPException

from rent_platform.config import settings
from rent_platform.db.session import db_fetch_one, db_fetch_all, db_execute
from rent_platform.db.repo import LedgerRepo, AccountRepo

router = APIRouter(prefix="/admin", tags=["admin"])


def _check_admin(x_admin_token: str | None) -> None:
    token = (x_admin_token or "").strip()
    if not token or token != (getattr(settings, "ADMIN_TOKEN", "") or "").strip():
        raise HTTPException(status_code=403, detail="Forbidden")


# =========================================================
# Platform settings (банер/фото в кабінеті + майбутні поля)
# =========================================================

@router.get("/platform-settings")
async def admin_get_platform_settings(x_admin_token: str | None = Header(default=None)):
    _check_admin(x_admin_token)
    q = """
    SELECT id, cabinet_banner_url, cabinet_banner_text, updated_ts
    FROM platform_settings
    WHERE id = 1
    """
    row = await db_fetch_one(q, {})
    return row or {"id": 1, "cabinet_banner_url": "", "cabinet_banner_text": "", "updated_ts": 0}


@router.post("/platform-settings")
async def admin_set_platform_settings(payload: dict, x_admin_token: str | None = Header(default=None)):
    """
    Можна оновити одразу кілька полів.
    Зараз підтримуємо:
      - cabinet_banner_url (фото/банер в кабінеті)
      - cabinet_banner_text (текст над/під банером на майбутнє)
    """
    _check_admin(x_admin_token)

    banner_url = str(payload.get("cabinet_banner_url") or "").strip()
    banner_text = str(payload.get("cabinet_banner_text") or "").strip()
    ts = int(time.time())

    q = """
    INSERT INTO platform_settings (id, cabinet_banner_url, cabinet_banner_text, updated_ts)
    VALUES (1, :u, :t, :ts)
    ON CONFLICT (id)
    DO UPDATE SET
      cabinet_banner_url = EXCLUDED.cabinet_banner_url,
      cabinet_banner_text = EXCLUDED.cabinet_banner_text,
      updated_ts = EXCLUDED.updated_ts
    """
    await db_execute(q, {"u": banner_url, "t": banner_text, "ts": ts})
    return {"ok": True, "cabinet_banner_url": banner_url, "cabinet_banner_text": banner_text, "updated_ts": ts}


@router.post("/cabinet-banner")
async def admin_set_cabinet_banner(payload: dict, x_admin_token: str | None = Header(default=None)):
    """
    Сумісний короткий ендпоінт (для простого використання):
    body: {"url":"https://..."}
    """
    _check_admin(x_admin_token)
    url = str(payload.get("url") or "").strip()
    ts = int(time.time())

    q = """
    INSERT INTO platform_settings (id, cabinet_banner_url, cabinet_banner_text, updated_ts)
    VALUES (1, :u, '', :ts)
    ON CONFLICT (id)
    DO UPDATE SET cabinet_banner_url = EXCLUDED.cabinet_banner_url,
                  updated_ts = EXCLUDED.updated_ts
    """
    await db_execute(q, {"u": url, "ts": ts})
    return {"ok": True, "cabinet_banner_url": url, "updated_ts": ts}


# =========================================================
# Withdraw requests (адмін-цикл)
# =========================================================

@router.get("/withdraws")
async def admin_list_withdraws(
    status: str | None = None,
    limit: int = 50,
    x_admin_token: str | None = Header(default=None),
):
    _check_admin(x_admin_token)

    status = (status or "").strip().lower()
    limit = max(1, min(200, int(limit)))

    params: dict[str, Any] = {"lim": limit}
    where = ""
    if status:
        where = "WHERE status = :st"
        params["st"] = status

    q = f"""
    SELECT id, owner_user_id, amount_kop, method, status, meta, created_ts, updated_ts
    FROM withdraw_requests
    {where}
    ORDER BY created_ts DESC
    LIMIT :lim
    """
    rows = await db_fetch_all(q, params)

    # meta може бути json-string
    out = []
    for r in rows or []:
        meta = r.get("meta") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        out.append({**r, "meta": meta})

    return {"items": out, "count": len(out)}


@router.post("/withdraws/{withdraw_id}/status")
async def admin_set_withdraw_status(
    withdraw_id: int,
    payload: dict,
    x_admin_token: str | None = Header(default=None),
):
    """
    body: {"status":"approved|rejected|paid", "note":"..."}
    Логіка:
      - pending -> approved: тільки статус + ledger
      - pending -> paid: статус + ledger
      - pending -> rejected: статус + REFUND (повертаємо гроші на withdraw_balance) + ledger
    """
    _check_admin(x_admin_token)

    new_status = str(payload.get("status") or "").strip().lower()
    note = str(payload.get("note") or "").strip()[:500]

    if new_status not in ("approved", "rejected", "paid"):
        raise HTTPException(status_code=400, detail="Bad status")

    # читаємо заявку
    q_get = """
    SELECT id, owner_user_id, amount_kop, method, status, meta, created_ts, updated_ts
    FROM withdraw_requests
    WHERE id = :id
    """
    req = await db_fetch_one(q_get, {"id": int(withdraw_id)})
    if not req:
        raise HTTPException(status_code=404, detail="Not found")

    cur_status = str(req.get("status") or "").strip().lower()
    if cur_status == new_status:
        return {"ok": True, "status": cur_status, "note": "no changes"}

    if cur_status not in ("pending", "approved"):
        # якщо вже paid/rejected — не чіпаємо
        raise HTTPException(status_code=409, detail=f"Cannot change from status={cur_status}")

    owner_id = int(req["owner_user_id"])
    amount_kop = int(req.get("amount_kop") or 0)

    # 1) оновлюємо статус
    q_upd = """
    UPDATE withdraw_requests
    SET status = :st,
        updated_ts = :ts
    WHERE id = :id
    """
    await db_execute(q_upd, {"st": new_status, "ts": int(time.time()), "id": int(withdraw_id)})

    # 2) ledger + refund (якщо rejected з pending)
    try:
        if new_status == "approved":
            await LedgerRepo.add(
                owner_id,
                "withdraw_approved",
                0,
                tenant_id=None,
                meta={"withdraw_id": int(withdraw_id), "note": note},
            )

        elif new_status == "paid":
            await LedgerRepo.add(
                owner_id,
                "withdraw_paid",
                0,
                tenant_id=None,
                meta={"withdraw_id": int(withdraw_id), "note": note},
            )

        elif new_status == "rejected":
            # повертаємо тільки якщо була pending (бо pending вже списав withdraw_balance)
            if cur_status == "pending" and amount_kop > 0:
                await AccountRepo.ensure(owner_id)

                q_refund = """
                UPDATE owner_accounts
                SET withdraw_balance_kop = withdraw_balance_kop + :a,
                    updated_ts = :ts
                WHERE owner_user_id = :uid
                RETURNING withdraw_balance_kop
                """
                await db_fetch_one(q_refund, {"uid": owner_id, "a": amount_kop, "ts": int(time.time())})

                await LedgerRepo.add(
                    owner_id,
                    "withdraw_rejected_refund",
                    +amount_kop,
                    tenant_id=None,
                    meta={"withdraw_id": int(withdraw_id), "note": note},
                )
            else:
                await LedgerRepo.add(
                    owner_id,
                    "withdraw_rejected",
                    0,
                    tenant_id=None,
                    meta={"withdraw_id": int(withdraw_id), "note": note},
                )
    except Exception:
        pass

    return {"ok": True, "id": int(withdraw_id), "from": cur_status, "to": new_status}


# =========================================================
# Accounts (view + adjust)
# =========================================================

@router.get("/accounts/{owner_user_id}")
async def admin_get_account(owner_user_id: int, x_admin_token: str | None = Header(default=None)):
    _check_admin(x_admin_token)
    owner_user_id = int(owner_user_id)

    await AccountRepo.ensure(owner_user_id)
    acc = await AccountRepo.get(owner_user_id)
    if not acc:
        return {"owner_user_id": owner_user_id, "balance_kop": 0, "withdraw_balance_kop": 0}

    return {
        "owner_user_id": owner_user_id,
        "balance_kop": int(acc.get("balance_kop") or 0),
        "withdraw_balance_kop": int(acc.get("withdraw_balance_kop") or 0),
        "updated_ts": int(acc.get("updated_ts") or 0),
    }


@router.post("/accounts/{owner_user_id}/adjust-balance")
async def admin_adjust_balance(
    owner_user_id: int,
    payload: dict,
    x_admin_token: str | None = Header(default=None),
):
    """
    body: {"delta_kop": 1000, "reason":"..."}
    delta_kop може бути від’ємним.
    """
    _check_admin(x_admin_token)

    owner_user_id = int(owner_user_id)
    delta_kop = int(payload.get("delta_kop") or 0)
    reason = str(payload.get("reason") or "").strip()[:500]

    if delta_kop == 0:
        raise HTTPException(status_code=400, detail="delta_kop must be non-zero")

    await AccountRepo.ensure(owner_user_id)

    q = """
    UPDATE owner_accounts
    SET balance_kop = balance_kop + :d,
        updated_ts = :ts
    WHERE owner_user_id = :uid
    RETURNING balance_kop
    """
    row = await db_fetch_one(q, {"uid": owner_user_id, "d": delta_kop, "ts": int(time.time())})
    new_balance = int((row or {}).get("balance_kop") or 0)

    try:
        await LedgerRepo.add(
            owner_user_id,
            "admin_adjust_balance",
            int(delta_kop),
            tenant_id=None,
            meta={"reason": reason},
        )
    except Exception:
        pass

    return {"ok": True, "owner_user_id": owner_user_id, "new_balance_kop": new_balance, "delta_kop": delta_kop}


# =========================================================
# Future: керування тарифами на кожен бот окремо (tenant override)
# =========================================================

@router.get("/tenants")
async def admin_list_tenants(
    status: str | None = None,
    owner_user_id: int | None = None,
    limit: int = 50,
    x_admin_token: str | None = Header(default=None),
):
    _check_admin(x_admin_token)

    limit = max(1, min(200, int(limit)))
    status = (status or "").strip().lower()

    where = []
    params: dict[str, Any] = {"lim": limit}

    if status:
        where.append("status = :st")
        params["st"] = status
    if owner_user_id is not None:
        where.append("owner_user_id = :uid")
        params["uid"] = int(owner_user_id)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    q = f"""
    SELECT id, owner_user_id, status, paused_reason, display_name, product_key, rate_per_min_kop, last_billed_ts, paid_until_ts
    FROM tenants
    {where_sql}
    ORDER BY created_ts DESC
    LIMIT :lim
    """
    rows = await db_fetch_all(q, params)
    return {"items": rows or [], "count": len(rows or [])}


@router.get("/tenants/{tenant_id}")
async def admin_get_tenant(tenant_id: str, x_admin_token: str | None = Header(default=None)):
    _check_admin(x_admin_token)
    q = """
    SELECT id, owner_user_id, status, paused_reason, display_name, product_key, rate_per_min_kop, last_billed_ts, paid_until_ts, created_ts
    FROM tenants
    WHERE id = :id
    """
    row = await db_fetch_one(q, {"id": str(tenant_id)})
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return row


@router.post("/tenants/{tenant_id}/rate")
async def admin_set_tenant_rate(
    tenant_id: str,
    payload: dict,
    x_admin_token: str | None = Header(default=None),
):
    """
    body: {"rate_per_min_kop": 0|int}
    0 або null -> прибирає override (буде тариф з PRODUCT_CATALOG)
    """
    _check_admin(x_admin_token)
    rpm = payload.get("rate_per_min_kop", 0)
    try:
        rpm_int = int(rpm or 0)
    except Exception:
        raise HTTPException(status_code=400, detail="Bad rate_per_min_kop")

    q = """
    UPDATE tenants
    SET rate_per_min_kop = :r
    WHERE id = :id
    """
    await db_execute(q, {"r": rpm_int, "id": str(tenant_id)})
    return {"ok": True, "tenant_id": str(tenant_id), "rate_per_min_kop": rpm_int}


@router.post("/tenants/{tenant_id}/product")
async def admin_set_tenant_product(
    tenant_id: str,
    payload: dict,
    x_admin_token: str | None = Header(default=None),
):
    """
    body: {"product_key": "shop"|...|null}
    """
    _check_admin(x_admin_token)
    pk = payload.get("product_key")
    pk = None if pk is None else str(pk).strip() or None

    q = """
    UPDATE tenants
    SET product_key = :pk
    WHERE id = :id
    """
    await db_execute(q, {"pk": pk, "id": str(tenant_id)})
    return {"ok": True, "tenant_id": str(tenant_id), "product_key": pk}