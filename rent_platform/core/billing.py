from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from aiogram import Bot

from rent_platform.db.repo import TenantRepo, AccountRepo, LedgerRepo
from rent_platform.products.catalog import PRODUCT_CATALOG

log = logging.getLogger(__name__)

NEGATIVE_LIMIT_KOP = -300          # -3 грн
BILL_TICK_SECONDS = 60
MAX_MINUTES_PER_RUN = 24 * 60      # політика: не доганяємо більше 1 доби за раз


def _floor_minutes(a_ts: int, b_ts: int) -> int:
    if b_ts <= a_ts:
        return 0
    return int((b_ts - a_ts) // 60)


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
    Рекомендація: виставити env TZ=Europe/Zaporozhye на Railway.
    """
    now = time.time()
    lt = time.localtime(now)
    tomorrow = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday + 1, 0, 0, 0, 0, 0, -1))
    return max(1, int(tomorrow - now))


async def billing_run_daily(platform_bot: Bot) -> None:
    """
    Раз на добу о 00:00:
    - беремо активні tenants (status='active' AND product_key not null)
    - рахуємо хвилини від last_billed_ts до now
    - списуємо rate_per_min * minutes
    - дозволяємо мінус до -3 грн
    - якщо не вистачає — частково списуємо до ліміту і ставимо pause billing
    - last_billed_ts:
        * full: now
        * partial: last_billed_ts + minutes_paid*60
        * pause: now (щоб у паузі не накопичувались хвилини)
    """
    now = int(time.time())
    tenants = await TenantRepo.list_active_for_billing()
    if not tenants:
        return

    # групуємо по owner
    by_owner: dict[int, list[dict[str, Any]]] = {}
    for t in tenants:
        by_owner.setdefault(int(t["owner_user_id"]), []).append(t)

    for owner_id, items in by_owner.items():
        await AccountRepo.ensure(owner_id)
        acc = await AccountRepo.get(owner_id)
        # локальний кеш балансу для partial-математики
        balance = int((acc or {}).get("balance_kop") or 0)

        charged_total = 0
        paused_cnt = 0
        charged_cnt = 0

        for t in items:
            tenant_id = str(t["id"])
            pk = t.get("product_key")
            if not pk:
                continue

            rate = _tenant_rate_kop(t)
            last_billed_ts = int(t.get("last_billed_ts") or 0)

            # 1) якщо тариф 0 — просто синхронізуємо last_billed_ts, щоб не накопичувалось
            if rate <= 0:
                await TenantRepo.set_rate_and_last_billed(owner_id, tenant_id, 0, now)
                continue

            # 2) якщо last_billed_ts = 0 (новий/старий запис) — ініціалізуємо і не списуємо
            if last_billed_ts <= 0:
                await TenantRepo.set_rate_and_last_billed(owner_id, tenant_id, int(rate), now)
                continue

            minutes = _floor_minutes(last_billed_ts, now)
            if minutes <= 0:
                continue

            # політика: максимум 1 доба за прогін (можна зняти clamp, якщо хочеш доганяти)
            if minutes > MAX_MINUTES_PER_RUN:
                minutes = MAX_MINUTES_PER_RUN

            need = int(rate) * int(minutes)
            if need <= 0:
                await TenantRepo.set_rate_and_last_billed(owner_id, tenant_id, int(rate), now)
                continue

            # 3) пробуємо списати повністю (атомарно з лімітом)
            new_balance = await AccountRepo.try_charge(owner_id, need, NEGATIVE_LIMIT_KOP)
            if new_balance is not None:
                # успіх: оновлюємо кеш і пишемо ledger
                balance = int(new_balance)
                charged_total += need
                charged_cnt += 1

                await TenantRepo.set_rate_and_last_billed(owner_id, tenant_id, int(rate), now)

                try:
                    await LedgerRepo.add(
                        owner_id,
                        "daily_charge",
                        -need,
                        tenant_id=tenant_id,
                        meta={"product_key": pk, "minutes": minutes, "rate_kop": int(rate), "from_ts": last_billed_ts, "to_ts": now},
                    )
                except Exception:
                    log.exception("ledger add failed owner=%s tenant=%s", owner_id, tenant_id)

                continue

            # 4) не вистачає: partial до ліміту (рахуємо по нашому кешу)
            max_charge = int(balance - NEGATIVE_LIMIT_KOP)  # скільки можемо списати, щоб не піти нижче ліміту
            if max_charge > 0:
                minutes_paid = int(max_charge // rate)
            else:
                minutes_paid = 0

            if minutes_paid > minutes:
                minutes_paid = minutes

            if minutes_paid > 0:
                charge = int(minutes_paid * rate)

                new_balance2 = await AccountRepo.try_charge(owner_id, charge, NEGATIVE_LIMIT_KOP)
                if new_balance2 is not None:
                    balance = int(new_balance2)
                    charged_total += charge
                    charged_cnt += 1

                    new_last = int(last_billed_ts + minutes_paid * 60)
                    await TenantRepo.set_rate_and_last_billed(owner_id, tenant_id, int(rate), new_last)

                    try:
                        await LedgerRepo.add(
                            owner_id,
                            "daily_charge_partial",
                            -charge,
                            tenant_id=tenant_id,
                            meta={
                                "product_key": pk,
                                "minutes_paid": minutes_paid,
                                "minutes_total": minutes,
                                "rate_kop": int(rate),
                                "limit_kop": NEGATIVE_LIMIT_KOP,
                                "from_ts": last_billed_ts,
                                "to_ts": now,
                            },
                        )
                    except Exception:
                        log.exception("ledger add partial failed owner=%s tenant=%s", owner_id, tenant_id)

            # 5) ставимо pause billing і “обнуляємо” накопичення часу в паузі (last_billed_ts = now)
            await TenantRepo.system_pause_billing(tenant_id)
            await TenantRepo.set_rate_and_last_billed(owner_id, tenant_id, int(rate), now)
            paused_cnt += 1

            await _send(
                platform_bot,
                owner_id,
                f"⏸ Оренда зупинена через недостатній баланс.\n"
                f"Бот: {tenant_id}\nПродукт: {pk}\nЛіміт мінуса: 3 грн.",
            )

        # зведення: тільки якщо реально щось списали або когось зупинили
        if charged_total > 0 or paused_cnt > 0:
            try:
                await _send(
                    platform_bot,
                    owner_id,
                    f"🧾 Білінг за добу виконано.\n"
                    f"Списано: {charged_total/100:.2f} грн\n"
                    f"Оренд списано: {charged_cnt}\n"
                    f"Зупинено через баланс: {paused_cnt}",
                )
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
    No-op loop, щоб main.py не падав на імпорті.
    """
    log.info("billing loop started (noop)")
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=BILL_TICK_SECONDS)
        except asyncio.TimeoutError:
            pass
    log.info("billing loop stopped (noop)")