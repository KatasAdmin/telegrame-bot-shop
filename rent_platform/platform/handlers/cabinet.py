from __future__ import annotations

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
    get_cabinet_banner_url,
    get_cabinet,
    create_withdraw_request,
    exchange_withdraw_to_main,
    cabinet_get_history,
    cabinet_get_tariffs,
)

log = logging.getLogger(__name__)

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

    banner_url = (await get_cabinet_banner_url()).strip()
    if banner_url:
        try:
            await message.answer_photo(
                photo=banner_url,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=cabinet_actions_kb(),
            )
            return
        except Exception as e:
            log.warning("cabinet banner failed url=%s err=%s", banner_url, e)

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
    # History
    # -------------------------
    @router.callback_query(F.data == "pl:cabinet:history")
    async def cb_cabinet_history(call: CallbackQuery) -> None:
        if not call.message:
            await call.answer()
            return

        items = await cabinet_get_history(call.from_user.id, limit=20)
        if not items:
            await call.message.answer(
                "📋 *Історія*\n\nПоки що порожньо 🙂",
                parse_mode="Markdown",
                reply_markup=back_to_menu_kb(),
            )
            await call.answer()
            return

        lines = ["📋 *Історія (останні 20)*", ""]
        for it in items:
            # it: {"ts":.., "title":.., "amount_str":.., "details":..}
            lines.append(f"• {it['title']}")
            if it.get("details"):
                lines.append(f"  _{it['details']}_")
            if it.get("amount_str") is not None:
                lines.append(f"  💰 *{it['amount_str']}*")
            lines.append("")  # пустий рядок між подіями

        await call.message.answer(
            "\n".join(lines).strip(),
            parse_mode="Markdown",
            reply_markup=back_to_menu_kb(),
        )
        await call.answer()

    # -------------------------
    # Tariffs
    # -------------------------
    @router.callback_query(F.data == "pl:cabinet:tariffs")
    async def cb_cabinet_tariffs(call: CallbackQuery) -> None:
        if not call.message:
            await call.answer()
            return

        data = await cabinet_get_tariffs(call.from_user.id)
        if not data:
            await call.message.answer("⚠️ Не знайшов ботів.", reply_markup=back_to_menu_kb())
            await call.answer()
            return

        lines = ["📈 *Тарифи*", ""]
        lines.append("Списання йде *1 раз на добу о 00:00* (сумарно за день).")
        lines.append("Якщо бот на паузі — *не списуємо*.")
        lines.append("Баланс може піти до *-3.00 грн* (тестовий мінус).")
        lines.append("")

        for b in data["bots"]:
            # b: {"name","id","status","rate_per_min_uah","rate_per_day_uah","note"}
            lines.append(f"• *{b['name']}*  (`{b['id']}`)")
            lines.append(f"  Статус: *{b['status']}*")
            lines.append(
                f"  Тариф: *{b['rate_per_min_uah']:.2f} грн/хв*  (~*{b['rate_per_day_uah']:.2f} грн/день*)"
            )
            if b.get("note"):
                lines.append(f"  _{b['note']}_")
            lines.append("")

        await call.message.answer(
            "\n".join(lines).strip(),
            parse_mode="Markdown",
            reply_markup=back_to_menu_kb(),
        )
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

    @router.message(ExchangeFlow.waiting_amount, F.text.in_(MENU_TEXTS))
    async def exchange_menu_pressed(message: Message, state: FSMContext) -> None:
        await state.clear()

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
            log.exception("withdraw failed: %s", e)
            await message.answer(
                "⚠️ Не вийшло створити заявку.\n"
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