from __future__ import annotations

import asyncio
import logging
import time

from aiogram import Bot

from rent_platform.db.repo import TenantRepo, AccountRepo, LedgerRepo
from rent_platform.products.catalog import PRODUCT_CATALOG

log = logging.getLogger(__name__)

# дозволяємо баланс йти в мінус до -3 грн
MIN_BALANCE_KOP = -300


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


def _tenant_rate_kop(t: dict) -> int:
    """
    Пріоритет тарифу:
    1) tenant.rate_per_min_kop (override) якщо > 0
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


def _next_midnight_ts(now_ts: int | None = None) -> int:
    """
    Наступна "північ" у локальному часі сервера.
    (Якщо Railway/сервер в UTC — то буде UTC-північ.)
    """
    now_ts = int(now_ts or time.time())
    lt = time.localtime(now_ts)

    # сьогоднішня дата 00:00
    today_midnight = int(
        time.mktime(
            (lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, lt.tm_wday, lt.tm_yday, lt.tm_isdst)
        )
    )

    # якщо вже після півночі — беремо завтра
    if now_ts >= today_midnight:
        return today_midnight + 24 * 3600

    return today_midnight


async def billing_run_daily(platform_bot: Bot) -> None:
    """
    Запуск раз на добу (о 00:00):
    - беремо всі active tenants з product_key
    - рахуємо скільки хвилин пройшло з last_billed_ts
    - списуємо одним платежем за день (або за кілька днів, якщо відстав)
    - дозволяємо мінус до -3 грн, потім billing pause
    - пишемо Ledger: kind='daily_charge'
    """
    now = int(time.time())

    tenants = await TenantRepo.list_active_for_billing()
    if not tenants:
        return

    # групуємо по власнику
    by_owner: dict[int, list[dict]] = {}
    for t in tenants:
        by_owner.setdefault(int(t["owner_user_id"]), []).append(t)

    for owner_id, items in by_owner.items():
        await AccountRepo.ensure(owner_id)
        acc = await AccountRepo.get(owner_id)
        balance = int((acc or {}).get("balance_kop") or 0)

        # 1) проходимось по кожному tenant
        for t in items:
            tenant_id = t["id"]
            pk = t.get("product_key")
            if not pk:
                continue

            rate = _tenant_rate_kop(t)
            if rate <= 0:
                # нульовий тариф — просто оновимо last_billed, щоб не накопичувати "борг часу"
                lb0 = int(t.get("last_billed_ts") or 0)
                if lb0 <= 0:
                    await TenantRepo.set_rate_and_last_billed(owner_id, tenant_id, 0, now)
                else:
                    await TenantRepo.set_rate_and_last_billed(owner_id, tenant_id, 0, now)
                continue

            last_billed = int(t.get("last_billed_ts") or 0)
            if last_billed <= 0:
                # перший запуск — стартуємо "зараз", щоб не списати заднім числом
                await TenantRepo.set_rate_and_last_billed(owner_id, tenant_id, rate, now)
                continue

            elapsed_min = max(0, (now - last_billed) // 60)
            if elapsed_min <= 0:
                continue

            need = elapsed_min * rate  # коп

            # 2) дозволяємо баланс до MIN_BALANCE_KOP
            # Якщо можемо списати повністю і не впасти нижче мінімуму — списуємо.
            if (balance - need) >= MIN_BALANCE_KOP:
                balance -= need
                await AccountRepo.set_balance(owner_id, balance)
                await LedgerRepo.add(
                    owner_id,
                    "daily_charge",
                    -need,
                    tenant_id=tenant_id,
                    meta={"product_key": pk, "minutes": elapsed_min, "rate_kop": rate},
                )
                await TenantRepo.set_rate_and_last_billed(owner_id, tenant_id, rate, last_billed + elapsed_min * 60)
                continue

            # 3) інакше списуємо МАКСИМУМ до мінімального балансу і ставимо паузу billing
            max_charge = balance - MIN_BALANCE_KOP  # скільки ще можна списати, щоб дійти до мінімуму
            if max_charge > 0:
                # скільки хвилин реально можемо покрити
                affordable_min = max_charge // rate if rate > 0 else 0
                if affordable_min > 0:
                    charge = affordable_min * rate
                    balance -= charge
                    await AccountRepo.set_balance(owner_id, balance)
                    await LedgerRepo.add(
                        owner_id,
                        "daily_charge",
                        -charge,
                        tenant_id=tenant_id,
                        meta={"product_key": pk, "minutes": affordable_min, "rate_kop": rate, "partial": True},
                    )
                    await TenantRepo.set_rate_and_last_billed(owner_id, tenant_id, rate, last_billed + affordable_min * 60)

            # ставимо на паузу billing (далі НЕ списуватиметься, бо list_active_for_billing бере тільки active)
            await TenantRepo.system_pause_billing(tenant_id)
            await _send(
                platform_bot,
                owner_id,
                f"⏸ Оренда зупинена через недостатній баланс.\n"
                f"Бот: {tenant_id}\n"
                f"Продукт: {pk}\n"
                f"Мінімальний баланс: -3 грн",
            )

        # (опційно) один короткий лог по власнику
        log.info("daily billing done owner=%s balance_kop=%s", owner_id, balance)


async def billing_daemon_daily_midnight(platform_bot: Bot, stop_event: asyncio.Event | None = None) -> None:
    """
    Демон: чекає до 00:00 і запускає billing_run_daily(), повторює щодня.
    """
    log.info("billing daemon (daily midnight) started")
    stop_event = stop_event or asyncio.Event()

    while not stop_event.is_set():
        now = int(time.time())
        next_midnight = _next_midnight_ts(now)
        sleep_s = max(1, next_midnight - now)

        log.info("billing daemon sleeping %s sec until midnight", sleep_s)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=sleep_s)
            break
        except asyncio.TimeoutError:
            pass

        try:
            await billing_run_daily(platform_bot)
        except Exception as e:
            log.exception("daily billing failed: %s", e)

    log.info("billing daemon stopped")