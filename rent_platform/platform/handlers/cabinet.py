from __future__ import annotations

import os
import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from rent_platform.platform.keyboards import (
    cabinet_actions_kb,
    back_to_menu_kb,
    BTN_MARKETPLACE,
    BTN_MY_BOTS,
    BTN_CABINET,
    BTN_PARTNERS,
    BTN_HELP,
)

from rent_platform.platform.storage import (
    get_cabinet,
    create_withdraw_request,
    exchange_withdraw_to_main,
)

log = logging.getLogger(__name__)
CABINET_BANNER_URL = os.getenv("CABINET_BANNER_URL", "").strip()

# Тексти, які НЕ мають оброблятися FSM "введи суму"
MENU_TEXTS = (
    "⬅️ В меню",
    "В меню",
    "Меню",
    "/start",
    BTN_MARKETPLACE,
    BTN_MY_BOTS,
    BTN_CABINET,
    BTN_PARTNERS,
    BTN_HELP,
)


class WithdrawFlow(StatesGroup):
    waiting_amount = State()


class ExchangeFlow(StatesGroup):
    waiting_amount = State()


async def render_cabinet(message: Message) -> None:
    user_id = message.from_user.id
    data = await get_cabinet(user_id)

    bots = data.get("bots") or []
    total_bots = len(bots)

    active_cnt = paused_cnt = deleted_cnt = other_cnt = 0
    for b in bots:
        st = (b.get("status") or "active").lower()
        if st == "active":
            active_cnt += 1
        elif st == "paused":
            paused_cnt += 1
        elif st == "deleted":
            deleted_cnt += 1
        else:
            other_cnt += 1

    balance_uah = int(data.get("balance_kop") or 0) / 100.0
    withdraw_uah = int(data.get("withdraw_balance_kop") or 0) / 100.0

    caption = (
        "💼 *Кабінет*\n\n"
        f"🆔 *Ваш ID:* `{user_id}`\n"
        "🤖 *Ваші боти:*\n"
        f"• *Всього:* *{total_bots}*\n"
        f"• *Запущено:* *{active_cnt}*\n"
        f"• *На паузі:* *{paused_cnt}*\n"
        f"• *Видалено:* *{deleted_cnt}*"
        + (f"\n• *Інші:* *{other_cnt}*" if other_cnt else "")
        + "\n\n"
        f"💳 *Основний рахунок:* *{balance_uah:.2f} грн*\n"
        f"💵 *Рахунок для виводу:* *{withdraw_uah:.2f} грн*"
    )

    if CABINET_BANNER_URL:
        await message.answer_photo(
            photo=CABINET_BANNER_URL,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=cabinet_actions_kb(),
        )
    else:
        await message.answer(
            caption,
            parse_mode="Markdown",
            reply_markup=cabinet_actions_kb(),
        )


def register_cabinet(router: Router) -> None:
    # -------------------------
    # Open cabinet
    # -------------------------
    @router.callback_query(F.data == "pl:cabinet")
    async def cb_cabinet(call: CallbackQuery) -> None:
        if call.message:
            try:
                await render_cabinet(call.message)
            except Exception as e:
                log.exception("cabinet failed: %s", e)
                await call.message.answer("⚠️ Кабінет тимчасово впав.", reply_markup=back_to_menu_kb())
        await call.answer()

    # -------------------------
    # Exchange (start)
    # -------------------------
    @router.callback_query(F.data == "pl:cabinet:exchange")
    async def cb_exchange_start(call: CallbackQuery, state: FSMContext) -> None:
        if call.message:
            await state.set_state(ExchangeFlow.waiting_amount)
            await call.message.answer(
                "♻️ *Обмін коштів*\n\n"
                "Переведемо кошти з *рахунку для виводу* → на *основний рахунок*.\n\n"
                "Введи суму в гривнях (цілим числом), наприклад: `200`",
                parse_mode="Markdown",
                reply_markup=back_to_menu_kb(),
            )
        await call.answer()

    # Якщо юзер тисне меню-кнопки під час state — просто виходимо зі state
    @router.message(ExchangeFlow.waiting_amount, F.text.in_(MENU_TEXTS))
    async def exchange_menu_pressed(message: Message, state: FSMContext) -> None:
        await state.clear()
        # нічого не відповідаємо — меню/кнопки зловляться іншими хендлерами

    # Якщо юзер ввів число
    @router.message(ExchangeFlow.waiting_amount, F.text.regexp(r"^\s*\d+\s*$"))
    async def exchange_receive_amount(message: Message, state: FSMContext) -> None:
        txt = (message.text or "").strip()
        amount = int(txt)

        if amount < 1:
            await message.answer("❌ Мінімум 1 грн. Спробуй ще раз.")
            return
        if amount > 200000:
            await message.answer("❌ Забагато 😄 Введи меншу суму.")
            return

        await message.answer("⏳ Обробляю...")

        try:
            res = await exchange_withdraw_to_main(message.from_user.id, amount_uah=amount)
        except Exception as e:
            log.exception("exchange failed: %s", e)
            await message.answer(
                "⚠️ Не вийшло виконати обмін.\n"
                "Ймовірно, недостатньо коштів на рахунку для виводу.",
                reply_markup=back_to_menu_kb(),
            )
            return

        await state.clear()

        new_main = int(res.get("new_balance_kop") or 0) / 100.0
        new_withdraw = int(res.get("new_withdraw_balance_kop") or 0) / 100.0
        moved = int(res.get("amount_kop") or (amount * 100)) / 100.0

        await message.answer(
            "✅ *Обмін виконано*\n\n"
            f"♻️ Переведено: *{moved:.2f} грн*\n"
            f"💳 Основний рахунок: *{new_main:.2f} грн*\n"
            f"💵 Рахунок для виводу: *{new_withdraw:.2f} грн*",
            parse_mode="Markdown",
            reply_markup=back_to_menu_kb(),
        )

        try:
            await render_cabinet(message)
        except Exception:
            pass

    # Якщо юзер ввів не число
    @router.message(ExchangeFlow.waiting_amount, F.text)
    async def exchange_invalid_input(message: Message) -> None:
        await message.answer("❌ Введи число в грн, напр. 200")

    # -------------------------
    # Withdraw (start)
    # -------------------------
    @router.callback_query(F.data == "pl:cabinet:withdraw")
    async def cb_withdraw_start(call: CallbackQuery, state: FSMContext) -> None:
        if call.message:
            await state.set_state(WithdrawFlow.waiting_amount)
            await call.message.answer(
                "💵 *Вивід коштів*\n\n"
                "Введи суму в гривнях (цілим числом), наприклад: `200`\n\n"
                "⚠️ Вивід можливий тільки з *рахунку для виводу*.",
                parse_mode="Markdown",
                reply_markup=back_to_menu_kb(),
            )
        await call.answer()

    @router.message(WithdrawFlow.waiting_amount, F.text.in_(MENU_TEXTS))
    async def withdraw_menu_pressed(message: Message, state: FSMContext) -> None:
        await state.clear()

    @router.message(WithdrawFlow.waiting_amount, F.text.regexp(r"^\s*\d+\s*$"))
    async def withdraw_receive_amount(message: Message, state: FSMContext) -> None:
        txt = (message.text or "").strip()
        amount = int(txt)

        if amount < 10:
            await message.answer("❌ Мінімум 10 грн. Спробуй ще раз.")
            return
        if amount > 200000:
            await message.answer("❌ Забагато 😄 Введи меншу суму.")
            return

        await message.answer("⏳ Створюю заявку...")

        try:
            res = await create_withdraw_request(message.from_user.id, amount_uah=amount, method="manual")
        except Exception as e:
            log.exception("exchange failed: %s", e)
            await message.answer(
                "⚠️ Не вийшло виконати обмін.\n"
                "Ймовірно, недостатньо коштів на рахунку для виводу.",
                reply_markup=back_to_menu_kb(),
            )
            return

        if not res:
            await message.answer(
                "⚠️ Не вийшло створити заявку.\n"
                "Перевір, чи вистачає коштів на рахунку для виводу.",
                reply_markup=back_to_menu_kb(),
            )
            return

        await state.clear()

        new_withdraw = int(res.get("new_withdraw_balance_kop") or 0) / 100.0
        withdraw_id = int(res.get("withdraw_id") or 0)

        await message.answer(
            "✅ *Заявку на вивід створено*\n\n"
            f"🧾 ID заявки: `{withdraw_id}`\n"
            f"💵 Сума: *{int(res.get('amount_uah') or amount)} грн*\n"
            "⏳ Статус: *pending*\n\n"
            f"💼 Новий баланс для виводу: *{new_withdraw:.2f} грн*\n\n"
            "_Далі заявка потрапить в адмін-панель для обробки (approve/reject/paid)._",
            parse_mode="Markdown",
            reply_markup=back_to_menu_kb(),
        )

        try:
            await render_cabinet(message)
        except Exception:
            pass

    @router.message(WithdrawFlow.waiting_amount, F.text)
    async def withdraw_invalid_input(message: Message) -> None:
        await message.answer("❌ Введи число в грн, напр. 200")