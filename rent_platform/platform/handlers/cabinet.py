from __future__ import annotations

import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from rent_platform.platform.keyboards import cabinet_actions_kb, back_to_menu_kb
from rent_platform.platform.storage import get_cabinet

CABINET_BANNER_URL = os.getenv("CABINET_BANNER_URL", "").strip()


def _md_escape(text: str) -> str:
    return (
        str(text)
        .replace("_", "\\_")
        .replace("*", "\\*")
        .replace("`", "\\`")
        .replace("[", "\\[")
    )


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
    @router.callback_query(F.data == "pl:cabinet")
    async def cb_cabinet(call: CallbackQuery) -> None:
        if call.message:
            try:
                await render_cabinet(call.message)
            except Exception:
                await call.message.answer("⚠️ Кабінет тимчасово впав.", reply_markup=back_to_menu_kb())
        await call.answer()