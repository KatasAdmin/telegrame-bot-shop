from __future__ import annotations

import json
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from rent_platform.config import settings
from rent_platform.db.repo import ReferralRepo
from rent_platform.db.repo import RefPayoutRepo

router = Router()

def is_admin(user_id: int) -> bool:
    s = (settings.ADMIN_USER_IDS or "").strip()
    if not s:
        return False
    allowed = {int(x.strip()) for x in s.split(",") if x.strip().isdigit()}
    return int(user_id) in allowed


from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def admin_ref_kb(s: dict) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(
            text=("✅ Увімкнено" if s.get("enabled") else "⛔️ Вимкнено"),
            callback_data="adm:ref:toggle",
        )
    )
    kb.row(
        InlineKeyboardButton(text="✏️ % з поповнень", callback_data="adm:ref:set:topup"),
        InlineKeyboardButton(text="✏️ % з білінгу", callback_data="adm:ref:set:billing"),
    )
    kb.row(
        InlineKeyboardButton(text="✏️ Мін. виплата", callback_data="adm:ref:set:minpayout"),
    )
    kb.row(
        InlineKeyboardButton(text="📥 Pending заявки", callback_data="adm:ref:payouts:pending"),
    )
    return kb.as_markup()

class AdminRefFlow(StatesGroup):
    waiting_value = State()

async def _render(message: Message) -> None:
    s = await ReferralRepo.get_settings()
    txt = (
        "🛠 *Адмін • Рефералка*\n\n"
        f"Статус: *{'ON ✅' if s['enabled'] else 'OFF ⛔️'}*\n"
        f"З поповнень: *{s['percent_topup_bps']/100:.2f}%*\n"
        f"З білінгу: *{s['percent_billing_bps']/100:.2f}%*\n"
        f"Мін. виплата: *{s['min_payout_kop']/100:.2f} грн*\n"
    )
    await message.answer(txt, parse_mode="Markdown", reply_markup=admin_ref_kb(s))

@router.message(F.text == "/admin_ref")
async def admin_ref_cmd(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    await _render(message)

@router.callback_query(F.data == "adm:ref:toggle")
async def adm_toggle(call: CallbackQuery) -> None:
    if not call.message or not is_admin(call.from_user.id):
        await call.answer()
        return
    s = await ReferralRepo.get_settings()
    s["enabled"] = not bool(s.get("enabled"))
    await ReferralRepo.set_settings(s)
    await call.message.answer("✅ Збережено.", reply_markup=None)
    await _render(call.message)
    await call.answer()

@router.callback_query(F.data.startswith("adm:ref:set:"))
async def adm_set(call: CallbackQuery, state: FSMContext) -> None:
    if not call.message or not is_admin(call.from_user.id):
        await call.answer()
        return
    key = call.data.split("adm:ref:set:", 1)[1]
    await state.set_state(AdminRefFlow.waiting_value)
    await state.update_data(adm_ref_key=key)

    prompts = {
        "topup": "Введи % з поповнень (напр. 5 або 5.5).",
        "billing": "Введи % з білінгу (напр. 2 або 1.25).",
        "minpayout": "Введи мін. виплату в грн (напр. 100).",
    }
    await call.message.answer("✏️ " + prompts.get(key, "Введи значення:"))
    await call.answer()

@router.message(AdminRefFlow.waiting_value, F.text)
async def adm_receive_value(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    data = await state.get_data()
    key = data.get("adm_ref_key")
    raw = (message.text or "").strip().replace(",", ".")
    await state.clear()

    s = await ReferralRepo.get_settings()

    try:
        if key in ("topup", "billing"):
            pct = float(raw)
            if pct < 0 or pct > 100:
                raise ValueError
            bps = int(round(pct * 100))  # 1% = 100 bps
            if key == "topup":
                s["percent_topup_bps"] = bps
            else:
                s["percent_billing_bps"] = bps

        elif key == "minpayout":
            uah = float(raw)
            if uah < 0:
                raise ValueError
            s["min_payout_kop"] = int(round(uah * 100))

        else:
            await message.answer("⚠️ Невідомий параметр.")
            return

        await ReferralRepo.set_settings(s)
        await message.answer("✅ Оновлено.")
        await _render(message)

    except Exception:
        await message.answer("❌ Невалідне значення. Спробуй ще раз командою /admin_ref")

@router.callback_query(F.data == "adm:ref:payouts:pending")
async def adm_pending(call: CallbackQuery) -> None:
    if not call.message or not is_admin(call.from_user.id):
        await call.answer()
        return

    items = await RefPayoutRepo.list_pending(limit=20)
    if not items:
        await call.message.answer("📭 Нема pending заявок.")
        await call.answer()
        return

    lines = ["📥 *Pending заявки* (до 20 шт)\n"]
    kb = InlineKeyboardBuilder()

    for it in items:
        rid = int(it["id"])
        referrer_id = int(it["referrer_id"])
        amount = int(it["amount_kop"]) / 100
        lines.append(f"• #{rid} — user `{referrer_id}` — *{amount:.2f} грн*")

        kb.row(
            InlineKeyboardButton(text=f"✅ Approve #{rid}", callback_data=f"adm:ref:payout:ok:{rid}"),
            InlineKeyboardButton(text=f"❌ Reject #{rid}", callback_data=f"adm:ref:payout:rej:{rid}"),
        )

    await call.message.answer("\n".join(lines), parse_mode="Markdown", reply_markup=kb.as_markup())
    await call.answer()

@router.callback_query(F.data.startswith("adm:ref:payout:ok:"))
async def adm_payout_ok(call: CallbackQuery) -> None:
    if not call.message or not is_admin(call.from_user.id):
        await call.answer()
        return
    rid = int(call.data.split("adm:ref:payout:ok:", 1)[1])
    ok = await RefPayoutRepo.approve(rid)
    await call.message.answer("✅ Approve OK" if ok else "⚠️ Не вийшло (може вже не pending).")
    await call.answer()

@router.callback_query(F.data.startswith("adm:ref:payout:rej:"))
async def adm_payout_rej(call: CallbackQuery) -> None:
    if not call.message or not is_admin(call.from_user.id):
        await call.answer()
        return
    rid = int(call.data.split("adm:ref:payout:rej:", 1)[1])
    ok = await RefPayoutRepo.reject(rid)
    await call.message.answer("❌ Rejected" if ok else "⚠️ Не вийшло (може вже не pending).")
    await call.answer()