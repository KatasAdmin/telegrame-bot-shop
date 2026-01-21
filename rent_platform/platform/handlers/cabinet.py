from __future__ import annotations

import os
from datetime import datetime

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from rent_platform.platform.keyboards import back_to_menu_kb, cabinet_actions_kb
from rent_platform.platform.storage import get_cabinet

CABINET_BANNER_URL = os.getenv("CABINET_BANNER_URL", "").strip()


def _fmt_ts(ts: int) -> str:
    if not ts:
        return "—"
    return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M")


def _md_escape(text: str) -> str:
    return (
        str(text)
        .replace("_", "\\_")
        .replace("*", "\\*")
        .replace("`", "\\`")
        .replace("[", "\\[")
    )


async def _render_cabinet(message: Message) -> None:
    user_id = message.from_user.id
    data = await get_cabinet(user_id)

    balance_uah = int(data.get("balance_kop") or 0) / 100.0
    withdraw_uah = int(data.get("withdraw_balance_kop") or 0) / 100.0
    active_bots = int(data.get("active_bots") or 0)

    caption = (
        "💼 *Кабінет*\n\n"
        f"🆔 *Ваш ID:* `{user_id}`\n"
        f"🦾 *Запущено ботів:* *{active_bots}*\n\n"
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
    @router.callback_query(F.data == "pl:cabinet")
    async def cb_cabinet(call: CallbackQuery) -> None:
        if call.message:
            await _render_cabinet(call.message)
        await call.answer()

    @router.callback_query(F.data == "pl:cabinet:topup")
    async def cb_cabinet_topup(call: CallbackQuery, state: FSMContext) -> None:
        # залишаємо як заглушку — ти вже маєш topup логіку в start.py
        if call.message:
            await call.message.answer("💳 Поповнення: зайди в меню поповнення (в тебе вже є flow).")
        await call.answer()

    @router.callback_query(F.data == "pl:cabinet:withdraw")
    async def cb_cabinet_withdraw(call: CallbackQuery) -> None:
        if call.message:
            await call.message.answer(
                "💵 *Вивід коштів*\n\n(скоро)\n\n"
                "Тут буде:\n"
                "• додати карту/реквізити\n"
                "• заявка на вивід\n"
                "• статуси виплат",
                parse_mode="Markdown",
                reply_markup=back_to_menu_kb(),
            )
        await call.answer()

    @router.callback_query(F.data == "pl:cabinet:exchange")
    async def cb_cabinet_exchange(call: CallbackQuery) -> None:
        if call.message:
            await call.message.answer(
                "♻️ *Обмін коштів*\n\n(скоро)\n\n"
                "Обмін з рахунку «для виводу» → на «основний».",
                parse_mode="Markdown",
                reply_markup=back_to_menu_kb(),
            )
        await call.answer()

    @router.callback_query(F.data == "pl:cabinet:history")
    async def cb_cabinet_history(call: CallbackQuery) -> None:
        if call.message:
            await call.message.answer(
                "📋 *Історія транзакцій*\n\n(скоро)\n\n"
                "Тут покажемо поповнення/списання/вивід/обмін.",
                parse_mode="Markdown",
                reply_markup=back_to_menu_kb(),
            )
        await call.answer()