from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from rent_platform.config import settings

router = Router()

def is_admin(user_id: int) -> bool:
    s = (getattr(settings, "ADMIN_USER_IDS", "") or "").strip()
    if not s:
        return False
    allowed = {int(x.strip()) for x in s.split(",") if x.strip().isdigit()}
    return int(user_id) in allowed


def admin_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="🤝 Партнерка (% / мін. виплата)", callback_data="adm:open:ref"),
    )
    kb.row(
        InlineKeyboardButton(text="💸 Pending виплати", callback_data="adm:open:payouts"),
    )
    kb.row(
        InlineKeyboardButton(text="🧩 Продукти маркетплейсу (скоро)", callback_data="adm:open:products"),
        InlineKeyboardButton(text="🖼 Банер кабінету (скоро)", callback_data="adm:open:banner"),
    )
    return kb.as_markup()

@router.message(F.text == "/admin")
async def admin_cmd(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    txt = (
        "⚙️ *Адмін-панель (MVP)*\n\n"
        "Обери дію 👇"
    )
    await message.answer(txt, parse_mode="Markdown", reply_markup=admin_menu_kb())

@router.callback_query(F.data.in_({"adm:open:products", "adm:open:banner"}))
async def admin_stub(call: CallbackQuery) -> None:
    if not call.message or not is_admin(call.from_user.id):
        await call.answer()
        return
    await call.message.answer("⏳ Це в роботі. Зараз доробимо наступним кроком 🙂")
    await call.answer()