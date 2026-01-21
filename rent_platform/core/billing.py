from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from aiogram import Bot

from rent_platform.db.repo import TenantRepo, AccountRepo, LedgerRepo
from rent_platform.products.catalog import PRODUCT_CATALOG

log = logging.getLogger(__name__)

# Дозволяємо мінус до -3 грн (для тесту купівлі / “пережити” день)
NEGATIVE_LIMIT_KOP = -300

# Для “порожнього” лупа (поки не потрібен) — щоб main не ламався імпортом
BILL_TICK_SECONDS = 60


def _product_rate_kop(product_key: str) -> int:
    meta = PRODUCT_CATALOG.get(product_key) or {}

    # 1) новий формат: int коп/хв
    if meta.get("rate_per_min_kop") is not None:
        try:
            return max(0, int(meta.get("rate_per_min_kop") or 0))
        except Exception:
            return 0

    # 2) старий формат: float грн/хв -> коп/хв
    try:
        uah = float(meta.get("rate_per_min_uah", 0) or 0)
    except Exception:
        uah = 0.0
    return max(0, int(round(uah * 100)))


def _tenant_rate_kop(t: dict[str, Any]) -> int:
    """
    Пріоритет тарифу:
    1) tenants.rate_per_min_kop (override) якщо > 0
    2) PRODUCT_CATALOG[product_key] rate (kop або uah)
    """
    pk = t.get("product_key")
    if not pk:
        return 0

    try:
        override = int(t.get("rate_per_min_kop") or 0)
    except Exception:
        override = 0

    if override > 0:
        return override

    return _product_rate_kop(str(pk))


async def _send(platform_bot: Bot, user_id: int, text: str) -> None:
    try:
        await platform_bot.send_message(chat_id=user_id, text=text)
    except Exception as e:
        log.warning("billing notify failed user=%s err=%s", user_id, e)


def _seconds_to_next_midnight_local() -> int:
    """
    Скільки секунд до наступної 00:00 (локальний час процеса/сервера).
    """
    now = time.time()
    lt = time.localtime(now)

    # завтра 00:00
    tomorrow = time.mktime(
        (lt.tm_year, lt.tm_mon, lt.tm_mday + 1, 0, 0, 0, 0, 0, -1)
    )
    sec = int(tomorrow - now)
    return max(1, sec)


async def billing_run_daily(platform_bot: Bot) -> None:
    """
    Раз на добу:
    - беремо активні tenants (status='active' AND product_key not null)
    - списуємо повну добу тарифу (rate_per_min * 1440)
    - дозволяємо мінус до -3 грн
    - якщо не вистачає — частково списуємо до ліміту і ставимо pause billing
    - пишемо ledger по кожному tenant
    """
    now = int(time.time())
    tenants = await TenantRepo.list_active_for_billing()
    if not tenants:
        return

    # згрупуємо по owner
    by_owner: dict[int, list[dict[str, Any]]] = {}
    for t in tenants:
        by_owner.setdefault(int(t["owner_user_id"]), []).append(t)

    for owner_id, items in by_owner.items():
        await AccountRepo.ensure(owner_id)
        acc = await AccountRepo.get(owner_id)
        balance = int((acc or {}).get("balance_kop") or 0)

        # для повідомлення — покажемо сумарний денний burn
        day_total_need = 0

        # списання по кожному tenant
        for t in items:
            tenant_id = str(t["id"])
            pk = t.get("product_key")
            if not pk:
                continue

            rate = _tenant_rate_kop(t)
            if rate <= 0:
                # безкоштовний
                await TenantRepo.set_rate_and_last_billed(owner_id, tenant_id, 0, now)
                continue

            need = int(rate) * 1440  # за добу
            day_total_need += need

            # якщо можемо списати повністю і не впасти нижче -3 грн
            if (balance - need) >= NEGATIVE_LIMIT_KOP:
                balance -= need
                await AccountRepo.set_balance(owner_id, balance)

                await LedgerRepo.add(
                    owner_id,
                    "daily_charge",
                    -need,
                    tenant_id=tenant_id,
                    meta={"product_key": pk, "minutes": 1440, "rate_kop": int(rate)},
                )
                await TenantRepo.set_rate_and_last_billed(owner_id, tenant_id, int(rate), now)
                continue

            # інакше — списуємо максимум до ліміту і ставимо pause billing
            max_charge = balance - NEGATIVE_LIMIT_KOP  # скільки можемо списати, щоб не піти нижче -3 грн
            if max_charge > 0:
                balance -= max_charge
                await AccountRepo.set_balance(owner_id, balance)

                minutes_paid = int(max_charge // rate) if rate > 0 else 0
                await LedgerRepo.add(
                    owner_id,
                    "daily_charge_partial",
                    -max_charge,
                    tenant_id=tenant_id,
                    meta={"product_key": pk, "minutes": minutes_paid, "rate_kop": int(rate), "limit_kop": NEGATIVE_LIMIT_KOP},
                )

            # пауза саме billing (manual не чіпаємо — але тут tenant був active)
            await TenantRepo.system_pause_billing(tenant_id)
            await TenantRepo.set_rate_and_last_billed(owner_id, tenant_id, int(rate), now)

            await _send(
                platform_bot,
                owner_id,
                f"⏸ Оренда зупинена через недостатній баланс.\nБот: {tenant_id}\nПродукт: {pk}\nЛіміт мінуса: 3 грн.",
            )

        # опційно: коротке зведення раз на день, якщо щось списували
        if day_total_need > 0:
            try:
                uah = day_total_need / 100.0
                await _send(platform_bot, owner_id, f"🧾 Списання тарифів за добу виконано. Орієнтовно: {uah:.2f} грн/день (за активні оренди).")
            except Exception:
                pass


async def billing_daemon_daily_midnight(platform_bot: Bot, stop_event: asyncio.Event) -> None:
    """
    Фоновий демон: чекає до 00:00 і запускає billing_run_daily().
    """
    log.info("billing daily daemon started")
    while not stop_event.is_set():
        try:
            sec = _seconds_to_next_midnight_local()
            log.info("billing daily daemon sleeping %s sec until midnight", sec)
            await asyncio.wait_for(stop_event.wait(), timeout=sec)
            break
        except asyncio.TimeoutError:
            pass

        if stop_event.is_set():
            break

        try:
            await billing_run_daily(platform_bot)
        except Exception as e:
            log.exception("billing daily run failed: %s", e)

    log.info("billing daily daemon stopped")


async def billing_loop(platform_bot: Bot, stop_event: asyncio.Event) -> None:
    """
    Зараз “порожній” loop (лише щоб main.py не падав на імпорті).
    Якщо захочеш — сюди можна додати попередження/моніторинг кожні N хв.
    """
    log.info("billing loop started (noop)")
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=BILL_TICK_SECONDS)
        except asyncio.TimeoutError:
            pass
    log.info("billing loop stopped (noop)")