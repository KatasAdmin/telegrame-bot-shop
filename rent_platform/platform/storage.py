from __future__ import annotations

import json
import datetime
import logging
import time
from typing import Any

from aiogram import Bot

from rent_platform.config import settings
from rent_platform.db.repo import (
    AccountRepo,
    InvoiceRepo,
    LedgerRepo,
    ModuleRepo,
    PlatformSettingsRepo,
    RefPayoutRepo,
    ReferralRepo,
    TenantIntegrationRepo,
    TenantRepo,
    TenantSecretRepo,
    WithdrawRepo,
)
from rent_platform.db.session import db_execute, db_fetch_one
from rent_platform.products.catalog import PRODUCT_CATALOG

log = logging.getLogger(__name__)


def _tenant_webhook_url(tenant_id: str, secret: str) -> str:
    base = settings.WEBHOOK_URL.rstrip("/")
    prefix = settings.TENANT_WEBHOOK_PREFIX.rstrip("/")
    return f"{base}{prefix}/{tenant_id}/{secret}"


def _mask(v: str | None) -> str:
    if not v:
        return "—"
    v = str(v)
    if len(v) <= 6:
        return "***"
    return f"{v[:3]}***{v[-3:]}"


def _uah_to_kop(amount_uah: int) -> int:
    return max(0, int(amount_uah) * 100)


def _kop_to_uah_str(kop: int) -> str:
    return f"{int(kop) / 100:.2f}"


# ======================================================================
# My bots
# ======================================================================

async def list_bots(user_id: int) -> list[dict]:
    return await TenantRepo.list_by_owner(user_id)


async def get_cabinet_banner_url() -> str:
    """
    Повертає URL картинки-банера для Кабінету (якщо задано в адмінці).
    """
    try:
        s = await PlatformSettingsRepo.get()
        return str((s or {}).get("cabinet_banner_url") or "").strip()
    except Exception:
        return ""

async def add_bot(user_id: int, token: str, name: str = "Bot", product_key: str | None = None) -> dict:
    """
    Створює tenant (орендованого бота), вмикає базові модулі та модуль продукту,
    ставить webhook на tenant-url.
    """
    tenant = await TenantRepo.create(owner_user_id=user_id, bot_token=token)

    # ім'я в UI
    await TenantRepo.set_display_name(user_id, tenant["id"], name)

    # ✅ базові модулі
    await ModuleRepo.enable(tenant["id"], "core")

    if product_key:
        await TenantRepo.set_product_key(user_id, tenant["id"], product_key)
        await ModuleRepo.enable(tenant["id"], product_key)
    else:
        await ModuleRepo.enable(tenant["id"], "shop")

    # webhook tenant-а
    url = _tenant_webhook_url(tenant["id"], tenant["secret"])
    tenant_bot = Bot(token=token)
    try:
        await tenant_bot.set_webhook(
            url,
            drop_pending_updates=False,
            allowed_updates=["message", "callback_query"],
        )
    finally:
        await tenant_bot.session.close()

    return {"id": tenant["id"], "name": name, "status": tenant["status"], "product_key": product_key}


async def pause_bot(user_id: int, bot_id: str) -> bool:
    row = await TenantRepo.get_token_secret_for_owner(user_id, bot_id)
    if not row:
        return False

    ok = await TenantRepo.set_status(user_id, bot_id, "paused", paused_reason="manual")
    if not ok:
        return False

    tenant_bot = Bot(token=row["bot_token"])
    try:
        await tenant_bot.delete_webhook(drop_pending_updates=True)
    finally:
        await tenant_bot.session.close()

    return True


async def resume_bot(user_id: int, bot_id: str) -> bool:
    row = await TenantRepo.get_token_secret_for_owner(user_id, bot_id)
    if not row:
        return False

    ok = await TenantRepo.set_status(user_id, bot_id, "active", paused_reason=None)
    if not ok:
        return False

    url = _tenant_webhook_url(bot_id, row["secret"])
    tenant_bot = Bot(token=row["bot_token"])
    try:
        await tenant_bot.set_webhook(
            url,
            drop_pending_updates=False,
            allowed_updates=["message", "callback_query"],
        )
    finally:
        await tenant_bot.session.close()

    return True


async def delete_bot(user_id: int, bot_id: str) -> bool:
    row = await TenantRepo.get_token_secret_for_owner(user_id, bot_id)
    if not row:
        return False

    ok = await TenantRepo.soft_delete(user_id, bot_id)
    if not ok:
        return False

    await TenantRepo.rotate_secret(user_id, bot_id)

    tenant_bot = Bot(token=row["bot_token"])
    try:
        await tenant_bot.delete_webhook(drop_pending_updates=True)
    finally:
        await tenant_bot.session.close()

    return True


# ======================================================================
# Marketplace (продукти)
# ======================================================================

async def list_marketplace_products() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for key, meta in PRODUCT_CATALOG.items():
        items.append(
            {
                "key": key,
                "title": meta["title"],
                "short": meta["short"],
                "rate_per_min_uah": meta.get("rate_per_min_uah", 0),
            }
        )
    return items


async def get_marketplace_product(product_key: str) -> dict[str, Any] | None:
    meta = PRODUCT_CATALOG.get(product_key)
    if not meta:
        return None
    return {
        "key": product_key,
        "title": meta["title"],
        "desc": meta["desc"],
        "rate_per_min_uah": meta.get("rate_per_min_uah", 0),
    }


async def buy_product(user_id: int, product_key: str) -> dict[str, Any] | None:
    meta = PRODUCT_CATALOG.get(product_key)
    if not meta:
        return None
    return {
        "product_key": product_key,
        "title": meta["title"],
        "desc": meta["desc"],
        "rate_per_min_uah": meta.get("rate_per_min_uah", 0),
    }


# ======================================================================
# Cabinet
# ======================================================================

async def get_cabinet(user_id: int) -> dict[str, Any]:
    now = int(time.time())

    await AccountRepo.ensure(user_id)
    acc = await AccountRepo.get(user_id)
    balance_kop = int((acc or {}).get("balance_kop") or 0)
    withdraw_kop = int((acc or {}).get("withdraw_balance_kop") or 0)

    items = await TenantRepo.list_by_owner(user_id)

    bots: list[dict[str, Any]] = []
    active_count = 0
    for it in items:
        st = (it.get("status") or "active").lower()
        if st == "active":
            active_count += 1

        plan = (it.get("plan_key") or "free")
        paid_until = int(it.get("paid_until_ts") or 0)
        expired = bool(paid_until and paid_until < now)

        bots.append(
            {
                "id": it["id"],
                "name": it.get("name") or "Bot",
                "status": st,
                "plan_key": plan,
                "paid_until_ts": paid_until,
                "paused_reason": it.get("paused_reason"),
                "product_key": it.get("product_key"),
                "expired": expired,
            }
        )

    return {
        "now": now,
        "user_id": user_id,
        "active_bots": active_count,
        "balance_kop": balance_kop,
        "withdraw_balance_kop": withdraw_kop,
        "bots": bots,
    }


async def create_payment_link(user_id: int, bot_id: str, months: int = 1) -> dict | None:
    row = await TenantRepo.get_token_secret_for_owner(user_id, bot_id)
    if not row:
        return None

    amount_uah = 100 * months
    return {
        "bot_id": bot_id,
        "months": months,
        "amount_uah": amount_uah,
        "pay_url": f"https://example.com/pay?bot_id={bot_id}&m={months}&a={amount_uah}",
        "created_ts": int(time.time()),
    }


# ======================================================================
# Exchange: withdraw -> main
# ======================================================================

async def exchange_withdraw_to_main(user_id: int, amount_uah: int) -> dict | None:
    """
    Обмін коштів з рахунку для виводу -> на основний рахунок.
    """
    amount_uah = int(amount_uah)
    if amount_uah < 1:
        return None
    if amount_uah > 200000:
        return None

    amount_kop = _uah_to_kop(amount_uah)

    await AccountRepo.ensure(user_id)

    # atomic update to avoid race conditions
    q = """
    UPDATE owner_accounts
    SET
      withdraw_balance_kop = withdraw_balance_kop - :a,
      balance_kop = balance_kop + :a,
      updated_ts = :ts
    WHERE owner_user_id = :uid
      AND withdraw_balance_kop >= :a
    RETURNING balance_kop, withdraw_balance_kop
    """
    row = await db_fetch_one(q, {"uid": int(user_id), "a": int(amount_kop), "ts": int(time.time())})
    if not row:
        return None

    # ledger (optional)
    try:
        await LedgerRepo.add(
            user_id,
            "exchange_withdraw_to_main",
            +amount_kop,
            tenant_id=None,
            meta={"amount_uah": amount_uah},
        )
    except Exception:
        pass

    return {
        "amount_kop": int(amount_kop),
        "new_balance_kop": int(row.get("balance_kop") or 0),
        "new_withdraw_balance_kop": int(row.get("withdraw_balance_kop") or 0),
    }

def _fmt_dt(ts: int) -> str:
    # YYYY-MM-DD HH:MM
    return datetime.datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M")


async def cabinet_get_history(user_id: int, limit: int = 20) -> list[dict]:
    await AccountRepo.ensure(user_id)
    rows = await LedgerRepo.list_last(user_id, limit=limit)

    out: list[dict] = []
    for r in rows or []:
        kind = (r.get("kind") or "").lower()
        amount_kop = int(r.get("amount_kop") or 0)
        ts = int(r.get("created_ts") or 0)
        tenant_id = r.get("tenant_id")
        meta = r.get("meta") or {}

        # якщо meta з БД приходить рядком — пробуємо розпарсити
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}

        sign = "+" if amount_kop > 0 else ""
        amount_str = f"{sign}{amount_kop/100:.2f} грн"

        title = kind
        details = _fmt_dt(ts)

        if kind == "topup":
            title = "💳 Поповнення"
            details = f"{_fmt_dt(ts)} • {meta.get('provider','')}".strip(" •")
        elif kind in ("daily_billing", "daily_charge", "daily_charge_partial", "daily_tariff"):
            title = "⏱ Списання за тариф"
            tname = f"бот: {tenant_id}" if tenant_id else ""
# якщо є meta minutes/rate — можна показати коротко
            mins = meta.get("minutes")
            rate = meta.get("rate_kop") or meta.get("rate_per_min_kop")
            extra = []
            if mins is not None:
                extra.append(f"{mins} хв")
            if rate is not None:
                try:
                    extra.append(f"{int(rate)/100:.2f} грн/хв")
                except Exception:
                    pass
            extra_s = (" • " + ", ".join(extra)) if extra else ""
            details = f"{_fmt_dt(ts)} • {tname}{extra_s}".strip(" •")

        elif kind == "exchange_withdraw_to_main":
            title = "♻️ Обмін (вивід → основний)"
            details = _fmt_dt(ts)
        elif kind == "withdraw_request":
            title = "💵 Заявка на вивід"
            wid = meta.get("withdraw_id")
            details = f"{_fmt_dt(ts)} • id: {wid}" if wid else _fmt_dt(ts)

        out.append(
            {
                "ts": ts,
                "title": title,
                "details": details,
                "amount_str": amount_str,
            }
        )

    return out


async def cabinet_get_tariffs(user_id: int) -> dict | None:
    items = await TenantRepo.list_by_owner(user_id)
    if not items:
        return None

    bots_out: list[dict] = []
    for it in items:
        st = (it.get("status") or "active").lower()
        name = it.get("name") or "Bot"

        # rate беремо з tenants.rate_per_min_kop якщо є, інакше — з PRODUCT_CATALOG по product_key
        rate_per_min_kop = it.get("rate_per_min_kop")
        if rate_per_min_kop is None:
            pk = it.get("product_key")
            meta = PRODUCT_CATALOG.get(pk or "")
            rpm_uah = float((meta or {}).get("rate_per_min_uah") or 0)
            rate_per_min_kop = int(rpm_uah * 100)
        else:
            rate_per_min_kop = int(rate_per_min_kop)

        rate_per_min_uah = rate_per_min_kop / 100.0
        rate_per_day_uah = rate_per_min_uah * 60.0 * 24.0

        note = None
        if st != "active":
            note = "На паузі тариф не списується."

        bots_out.append(
            {
                "id": it["id"],
                "name": name,
                "status": st,
                "rate_per_min_uah": rate_per_min_uah,
                "rate_per_day_uah": rate_per_day_uah,
                "note": note,
            }
        )

    return {"bots": bots_out}

# ======================================================================
# Admin helpers (future: тарифи на кожен bot окремо)
# ======================================================================

async def admin_set_tenant_rate(tenant_id: str, rate_per_min_kop: int | None) -> None:
    """
    0/None -> прибирає override, тариф береться з PRODUCT_CATALOG по product_key
    """
    r = int(rate_per_min_kop or 0)
    q = "UPDATE tenants SET rate_per_min_kop = :r WHERE id = :id"
    await db_execute(q, {"r": r, "id": str(tenant_id)})


async def admin_set_tenant_product(tenant_id: str, product_key: str | None) -> None:
    """
    None/"" -> прибирає product_key (tenant не буде білитись, бо list_active_for_billing фільтрує product_key IS NOT NULL)
    """
    pk = None if not (product_key or "").strip() else str(product_key).strip()
    q = "UPDATE tenants SET product_key = :pk WHERE id = :id"
    await db_execute(q, {"pk": pk, "id": str(tenant_id)})

# ======================================================================
# TopUp (інвойси)
# ======================================================================

async def create_topup_invoice(user_id: int, amount_uah: int, provider: str) -> dict | None:
    amount_uah = int(amount_uah)
    if amount_uah < 10:
        return None
    if provider not in ("mono", "privat", "cryptobot"):
        return None

    amount_kop = _uah_to_kop(amount_uah)
    pay_url = f"https://example.com/topup?u={user_id}&a={amount_uah}&p={provider}"

    inv = await InvoiceRepo.create(
        owner_user_id=user_id,
        provider=provider,
        amount_kop=amount_kop,
        pay_url=pay_url,
        meta={"amount_uah": amount_uah, "provider": provider},
    )

    log.info("TOPUP invoice created: uid=%s inv=%s", user_id, inv)

    if not inv or not inv.get("id"):
        return None

    return {
        "invoice_id": int(inv["id"]),
        "provider": provider,
        "amount_uah": amount_uah,
        "amount_kop": amount_kop,
        "pay_url": pay_url,
        "created_ts": int(inv.get("created_ts") or 0),
    }


async def confirm_topup_paid_test(user_id: int, invoice_id: int) -> dict | None:
    """
    Тестовий confirm: імітуємо оплату інвойса.

    Гарантії:
    - no double credit: only the FIRST call can flip invoice pending->paid (UPDATE ... WHERE status='pending')
    - idempotent: all other calls return already=True without changing balance
    - after credit: auto-resume tenants paused by billing
    """
    invoice_id = int(invoice_id)

    # 0) Перевіряємо, що інвойс існує і належить юзеру (для UI/статусу)
    inv = await InvoiceRepo.get_for_owner(user_id, invoice_id)
    log.info("TOPUP confirm requested: uid=%s invoice_id=%s inv=%s", user_id, invoice_id, inv)
    if not inv:
        return None

    # helper: збирає баланс + пробує auto-resume + список paused billing
    async def _build_already_response(status: str) -> dict:
        await AccountRepo.ensure(user_id)
        acc = await AccountRepo.get(user_id)
        balance_kop = int((acc or {}).get("balance_kop") or 0)

        resumed_cnt = 0
        try:
            resumed_cnt = int(await TenantRepo.system_resume_all_billing_for_owner(user_id) or 0)
        except Exception:
            resumed_cnt = 0

        bots = await TenantRepo.list_by_owner(user_id)
        paused_billing_ids: list[str] = []
        for b in bots or []:
            st = (b.get("status") or "").lower()
            reason = (b.get("paused_reason") or "").lower()
            if st == "paused" and reason == "billing":
                paused_billing_ids.append(b["id"])

        return {
            "already": True,
            "status": (status or "").lower(),
            "new_balance_kop": balance_kop,
            "amount_kop": 0,
            "resumed_cnt": resumed_cnt,
            "paused_billing_ids": paused_billing_ids,
        }

    # 1) Швидка ідемпотентність по ledger (дешево і корисно)
    #    Але це НЕ основний захист (основний — UPDATE pending->paid).
    try:
        if await LedgerRepo.has_topup_invoice(user_id, invoice_id):
            return await _build_already_response((inv.get("status") or "").lower())
    except Exception:
        pass

    # 2) ОСНОВНИЙ захист від double credit:
    #    намагаємось атомарно pending -> paid.
    q = """
    UPDATE billing_invoices
    SET status = 'paid',
        paid_ts = :ts
    WHERE id = :id
      AND owner_user_id = :uid
      AND status = 'pending'
    RETURNING id, owner_user_id, provider, amount_kop, status
    """
    paid_row = await db_fetch_one(q, {"id": invoice_id, "uid": int(user_id), "ts": int(time.time())})

    if not paid_row:
        # або вже paid / canceled / не pending — НІЧОГО не донараховуємо
        return await _build_already_response((inv.get("status") or "").lower())

    amount_kop = int(paid_row.get("amount_kop") or 0)
    provider = paid_row.get("provider") or inv.get("provider")
    if amount_kop <= 0:
        # дуже дивно, але безпечніше не нараховувати
        return await _build_already_response("paid")

    # 3) Зарахування балансу (після того як інвойс вже "зафіксовано" як paid)
    await AccountRepo.add_balance(user_id, +amount_kop)

    # 4) Ledger topup (тепер уже точно один раз)
    try:
        await LedgerRepo.add(
            user_id,
            "topup",
            +amount_kop,
            tenant_id=None,
            meta={"invoice_id": invoice_id, "provider": provider},
        )
    except Exception:
        # якщо ledger впав — баланс вже поповнений.
        # для MVP ок, але в логах хай буде видно
        log.exception("Ledger topup insert failed: uid=%s invoice_id=%s", user_id, invoice_id)

    # 5) Рефералка (не ламає топап)
    try:
        await ReferralRepo.apply_commission(
            user_id=user_id,
            kind="topup",
            amount_kop=amount_kop,
            event_key=f"topup:{invoice_id}",
            title="Партнерка з поповнення",
            details=f"invoice_id={invoice_id}, provider={provider}",
        )
    except Exception:
        log.exception("Referral commission failed for topup invoice_id=%s uid=%s", invoice_id, user_id)

    # 6) Auto-resume після поповнення
    resumed_cnt = 0
    try:
        resumed_cnt = int(await TenantRepo.system_resume_all_billing_for_owner(user_id) or 0)
    except Exception:
        resumed_cnt = 0

    # 7) Повертаємо баланс і список тих, хто ще на billing pause
    await AccountRepo.ensure(user_id)
    acc = await AccountRepo.get(user_id)
    new_balance = int((acc or {}).get("balance_kop") or 0)

    bots = await TenantRepo.list_by_owner(user_id)
    paused_billing_ids: list[str] = []
    for b in bots or []:
        st = (b.get("status") or "").lower()
        reason = (b.get("paused_reason") or "").lower()
        if st == "paused" and reason == "billing":
            paused_billing_ids.append(b["id"])

    return {
        "ok": True,
        "new_balance_kop": new_balance,
        "amount_kop": amount_kop,
        "resumed_cnt": resumed_cnt,
        "paused_billing_ids": paused_billing_ids,
    }


# ======================================================================
# Tenant config (інтеграції + секрети)
# ======================================================================

SUPPORTED_PROVIDERS: dict[str, dict[str, Any]] = {
    "mono": {
        "title": "🏦 Mono",
        "secrets": [
            ("mono.token", "Mono API token"),
        ],
    },
    "privat": {
        "title": "🏦 Privat",
        "secrets": [
            ("privat.token", "Privat API token"),
        ],
    },
    "cryptobot": {
        "title": "🪙 CryptoBot",
        "secrets": [
            ("cryptobot.token", "CryptoBot token"),
        ],
    },
}


async def get_bot_config(user_id: int, bot_id: str) -> dict | None:
    row = await TenantRepo.get_token_secret_for_owner(user_id, bot_id)
    if not row:
        return None
    if (row.get("status") or "").lower() == "deleted":
        return None

    ints = await TenantIntegrationRepo.list_all(bot_id)
    enabled_map = {x["provider"]: bool(x["enabled"]) for x in ints}

    providers: list[dict[str, Any]] = []
    for p, meta in SUPPORTED_PROVIDERS.items():
        providers.append(
            {
                "provider": p,
                "title": meta["title"],
                "enabled": bool(enabled_map.get(p, False)),
                "secrets": [
                    {
                        "key": sk,
                        "label": lbl,
                        "value_masked": _mask((await TenantSecretRepo.get(bot_id, sk) or {}).get("secret_value")),
                    }
                    for sk, lbl in meta["secrets"]
                ],
            }
        )

    return {"bot_id": bot_id, "status": row.get("status"), "providers": providers}


async def toggle_integration(user_id: int, bot_id: str, provider: str) -> bool:
    if provider not in SUPPORTED_PROVIDERS:
        return False
    row = await TenantRepo.get_token_secret_for_owner(user_id, bot_id)
    if not row:
        return False
    if (row.get("status") or "").lower() == "deleted":
        return False

    cur = await TenantIntegrationRepo.get(bot_id, provider)
    new_enabled = not bool(cur.get("enabled")) if cur else True
    await TenantIntegrationRepo.set_enabled(bot_id, provider, new_enabled)
    return True


async def set_bot_secret(user_id: int, bot_id: str, secret_key: str, secret_value: str) -> bool:
    allowed = set()
    for meta in SUPPORTED_PROVIDERS.values():
        for sk, _lbl in meta["secrets"]:
            allowed.add(sk)
    if secret_key not in allowed:
        return False

    row = await TenantRepo.get_token_secret_for_owner(user_id, bot_id)
    if not row:
        return False
    if (row.get("status") or "").lower() == "deleted":
        return False

    await TenantSecretRepo.upsert(bot_id, secret_key, secret_value.strip())
    return True


# ======================================================================
# Withdraw (заявки)
# ======================================================================

async def _set_withdraw_balance_safe(user_id: int, new_withdraw_kop: int) -> None:
    """
    Якщо в твоєму AccountRepo є set_withdraw_balance — викличемо його.
    Якщо нема — зробимо напряму SQL.
    """
    fn = getattr(AccountRepo, "set_withdraw_balance", None)
    if callable(fn):
        await fn(user_id, int(new_withdraw_kop))
        return

    q = """
    UPDATE owner_accounts
    SET withdraw_balance_kop = :w, updated_ts = :ts
    WHERE owner_user_id = :uid
    """
    await db_execute(q, {"uid": int(user_id), "w": int(new_withdraw_kop), "ts": int(time.time())})


async def create_withdraw_request(user_id: int, amount_uah: int, method: str = "manual") -> dict | None:
    """
    Створює заявку на вивід (pending) і одразу списує гроші з withdraw_balance_kop.
    """
    amount_uah = int(amount_uah)
    if amount_uah < 10:
        return None

    amount_kop = _uah_to_kop(amount_uah)

    await AccountRepo.ensure(user_id)
    acc = await AccountRepo.get(user_id)
    withdraw_kop = int((acc or {}).get("withdraw_balance_kop") or 0)

    if amount_kop <= 0 or amount_kop > withdraw_kop:
        return None

    req = await WithdrawRepo.create(
        owner_user_id=user_id,
        amount_kop=amount_kop,
        method=method,
        meta={"amount_uah": amount_uah},
    )

    if not req or not req.get("id"):
        return None

    new_withdraw = withdraw_kop - amount_kop
    await _set_withdraw_balance_safe(user_id, new_withdraw)

    try:
        await LedgerRepo.add(
            user_id,
            "withdraw_request",
            -amount_kop,
            tenant_id=None,
            meta={"withdraw_id": int(req["id"]), "method": method},
        )
    except Exception:
        pass

    return {
        "withdraw_id": int(req["id"]),
        "status": "pending",
        "amount_uah": amount_uah,
        "amount_kop": amount_kop,
        "new_withdraw_balance_kop": new_withdraw,
        "created_ts": int(req.get("created_ts") or 0),
    }

def _kop_to_uah(kop: int) -> float:
    return float(int(kop)) / 100.0


# ======================================================================
# Partners (referral) helpers for handlers/start.py
# ======================================================================

async def partners_get_link(user_id: int, bot_username: str) -> str:
    return f"https://t.me/{bot_username}?start=ref_{int(user_id)}"


async def partners_get_stats(user_id: int) -> dict:
    st = await ReferralRepo.stats(int(user_id))
    settings = await ReferralRepo.get_settings()
    return {"stats": st, "settings": settings}


async def partners_create_payout(
    user_id: int,
    amount_kop: int | None = None,
    amount_uah: int | None = None,
    note: str = "",
) -> dict | None:
    """
    Приймає або amount_kop, або amount_uah (сумісність).
    start.py зараз шле amount_kop — це ок.
    """
    if amount_kop is None:
        amount_uah = int(amount_uah or 0)
        if amount_uah < 1 or amount_uah > 200000:
            return None
        amount_kop = amount_uah * 100

    amount_kop = int(amount_kop)
    if amount_kop < 100:  # < 1 грн
        return None
    if amount_kop > 200000 * 100:
        return None

    return await RefPayoutRepo.create_request(int(user_id), amount_kop, note=note)