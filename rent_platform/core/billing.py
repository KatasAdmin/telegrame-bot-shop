from __future__ import annotations

import asyncio
import logging
import time

from aiogram import Bot

from rent_platform.db.repo import TenantRepo, AccountRepo, LedgerRepo
from rent_platform.products.catalog import PRODUCT_CATALOG

log = logging.getLogger(__name__)

BILL_TICK_SECONDS = 30


def _product_rate_kop(product_key: str) -> int:
    meta = PRODUCT_CATALOG.get(product_key) or {}
    # підтримка старого поля rate_per_min_uah (float) і нового rate_per_min_kop (int)
    if "rate_per_min_kop" in meta:
        return int(meta["rate_per_min_kop"] or 0)
    uah = float(meta.get("rate_per_min_uah", 0) or 0)
    return int(round(uah * 100))


async def _send(platform_bot: Bot, user_id: int, text: str) -> None:
    try:
        await platform_bot.send_message(chat_id=user_id, text=text)
    except Exception as e:
        log.warning("billing notify failed user=%s err=%s", user_id, e)


async def billing_tick(platform_bot: Bot) -> None:
    now = int(time.time())

    tenants = await TenantRepo.list_active_for_billing()
    if not tenants:
        return

    # згрупуємо по owner
    by_owner: dict[int, list[dict]] = {}
    for t in tenants:
        by_owner.setdefault(int(t["owner_user_id"]), []).append(t)

    for owner_id, items in by_owner.items():
        await AccountRepo.ensure(owner_id)
        acc = await AccountRepo.get(owner_id)
        balance = int((acc or {}).get("balance_kop") or 0)

        # burn rate для попереджень (сума ставок активних)
        burn_per_min = 0
        for t in items:
            pk = t.get("product_key")
            if not pk:
                continue
            r = int(t.get("rate_per_min_kop") or 0)
            if r <= 0:
                r = _product_rate_kop(pk)
            burn_per_min += max(r, 0)

        # Попередження (24h / 3h) — тільки якщо є burn rate
        if burn_per_min > 0:
            minutes_left = balance // burn_per_min if burn_per_min > 0 else 10**9
            hours_left = minutes_left / 60.0

            # якщо хоч один tenant ще не попереджений — попередимо (запишемо в tenants warned_* щоб не спамити)
            if hours_left <= 24:
                for t in items:
                    if int(t.get("warned_24h_ts") or 0) == 0:
                        await TenantRepo.set_warned(owner_id, t["id"], "24h", now)
                await _send(platform_bot, owner_id, "⏳ Баланс може закінчитись менш ніж за 24 години при поточних орендах.")

            if hours_left <= 3:
                for t in items:
                    if int(t.get("warned_3h_ts") or 0) == 0:
                        await TenantRepo.set_warned(owner_id, t["id"], "3h", now)
                await _send(platform_bot, owner_id, "⚠️ Баланс може закінчитись менш ніж за 3 години при поточних орендах!")

        # Списання по кожному tenant
        for t in items:
            tenant_id = t["id"]
            pk = t.get("product_key")
            if not pk:
                continue

            rate = int(t.get("rate_per_min_kop") or 0)
            if rate <= 0:
                rate = _product_rate_kop(pk)

            if rate <= 0:
                continue  # безкоштовний/нульовий продукт

            last_billed = int(t.get("last_billed_ts") or 0)
            if last_billed <= 0:
                # перший білінг стартує "зараз", щоб не списати заднім числом
                await TenantRepo.set_rate_and_last_billed(owner_id, tenant_id, rate, now)
                continue

            elapsed_min = max(0, (now - last_billed) // 60)
            if elapsed_min <= 0:
                continue

            need = elapsed_min * rate

            if balance >= need:
                # списуємо повністю
                balance -= need
                await AccountRepo.set_balance(owner_id, balance)
                await LedgerRepo.add(owner_id, "charge", -need, tenant_id=tenant_id, meta={"product_key": pk, "minutes": elapsed_min, "rate_kop": rate})
                await TenantRepo.set_rate_and_last_billed(owner_id, tenant_id, rate, last_billed + elapsed_min * 60)
            else:
                # не вистачає — списуємо максимум можливого і пауза billing
                affordable_min = balance // rate if rate > 0 else 0
                if affordable_min > 0:
                    charge = affordable_min * rate
                    balance -= charge
                    await AccountRepo.set_balance(owner_id, balance)
                    await LedgerRepo.add(owner_id, "charge", -charge, tenant_id=tenant_id, meta={"product_key": pk, "minutes": affordable_min, "rate_kop": rate})
                    await TenantRepo.set_rate_and_last_billed(owner_id, tenant_id, rate, last_billed + affordable_min * 60)

                await TenantRepo.system_pause_billing(tenant_id)
                await _send(platform_bot, owner_id, f"⏸ Оренда зупинена через 0 баланс. Бот: {tenant_id} (продукт {pk})")


async def billing_loop(platform_bot: Bot, stop_event: asyncio.Event) -> None:
    log.info("billing loop started")
    while not stop_event.is_set():
        try:
            await billing_tick(platform_bot)
        except Exception as e:
            log.exception("billing tick failed: %s", e)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=BILL_TICK_SECONDS)
        except asyncio.TimeoutError:
            pass
    log.info("billing loop stopped")