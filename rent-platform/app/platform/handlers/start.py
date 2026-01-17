# app/platform/handlers/start.py
from __future__ import annotations

from aiogram import Router, F, types
from aiogram.filters import CommandStart

from platform.keyboards import platform_home_kb, market_kb, mybots_kb, back_home_kb

router = Router()


def _home_text() -> str:
    return (
        "🏗 <b>Rent Platform</b>\n\n"
        "Тут ти можеш:\n"
        "• орендувати готового бота\n"
        "• підключити модулі (магазин / інвест / фріланс)\n"
        "• керувати токеном, доступами та конфігом\n\n"
        "Обери розділ нижче 👇"
    )


@router.message(CommandStart())
async def pf_start(m: types.Message):
    await m.answer(_home_text(), parse_mode="HTML", reply_markup=platform_home_kb())


@router.callback_query(F.data == "pf:home")
async def pf_home(cb: types.CallbackQuery):
    try:
        await cb.message.edit_text(_home_text(), parse_mode="HTML", reply_markup=platform_home_kb())
    except Exception:
        await cb.message.answer(_home_text(), parse_mode="HTML", reply_markup=platform_home_kb())
    await cb.answer()


@router.callback_query(F.data == "pf:market")
async def pf_market(cb: types.CallbackQuery):
    txt = (
        "🛒 <b>Маркетплейс ботів</b>\n\n"
        "Оберіть, який модуль хочете орендувати.\n"
        "Після оренди ти зможеш:\n"
        "• підключити свій токен\n"
        "• налаштувати адмінів/персонал\n"
        "• керувати конфігом\n"
    )
    try:
        await cb.message.edit_text(txt, parse_mode="HTML", reply_markup=market_kb())
    except Exception:
        await cb.message.answer(txt, parse_mode="HTML", reply_markup=market_kb())
    await cb.answer()


@router.callback_query(F.data == "pf:mybots")
async def pf_mybots(cb: types.CallbackQuery):
    txt = (
        "⚙️ <b>Мої боти (оренда)</b>\n\n"
        "Тут буде список твоїх орендованих ботів.\n"
        "Поки що це скелет — далі зробимо:\n"
        "• додавання токена\n"
        "• підключення модуля (shop/invest/…)\n"
        "• ролі (адмін/менеджер/пакувальник)\n"
        "• конфіг кнопок/текстів\n"
    )
    try:
        await cb.message.edit_text(txt, parse_mode="HTML", reply_markup=mybots_kb())
    except Exception:
        await cb.message.answer(txt, parse_mode="HTML", reply_markup=mybots_kb())
    await cb.answer()


@router.callback_query(F.data == "pf:profile")
async def pf_profile(cb: types.CallbackQuery):
    u = cb.from_user
    txt = (
        "👤 <b>Профіль</b>\n\n"
        f"ID: <code>{u.id}</code>\n"
        f"Username: <code>@{u.username}</code>\n"
        f"Name: <b>{(u.full_name or '—')}</b>\n\n"
        "Пізніше тут буде:\n"
        "• статус підписки\n"
        "• баланс/оплати\n"
        "• ліміти\n"
    )
    try:
        await cb.message.edit_text(txt, parse_mode="HTML", reply_markup=back_home_kb())
    except Exception:
        await cb.message.answer(txt, parse_mode="HTML", reply_markup=back_home_kb())
    await cb.answer()


@router.callback_query(F.data == "pf:billing")
async def pf_billing(cb: types.CallbackQuery):
    # Заглушка під майбутні платежі
    txt = (
        "💳 <b>Оплата / Тарифи</b>\n\n"
        "Поки що не підключено.\n"
        "Далі зробимо 2 варіанти:\n"
        "1) Telegram Payments (Stripe/WayForPay/…)\n"
        "2) ручна оплата + автопродовження по статусу\n\n"
        "Коли ти будеш готовий — підключимо одразу нормально ✅"
    )
    try:
        await cb.message.edit_text(txt, parse_mode="HTML", reply_markup=back_home_kb())
    except Exception:
        await cb.message.answer(txt, parse_mode="HTML", reply_markup=back_home_kb())
    await cb.answer()


# --- Marketplace items (заглушки) ---

@router.callback_query(F.data.startswith("pf:market:"))
async def pf_market_item(cb: types.CallbackQuery):
    item = cb.data.split(":", 2)[2]  # shop / invest / freelance
    title = {"shop": "🛍 Магазин-бот", "invest": "📈 Інвест-бот", "freelance": "💼 Фріланс-бот"}.get(item, "Модуль")

    txt = (
        f"{title}\n\n"
        "Це сторінка модуля.\n"
        "Тут буде:\n"
        "• опис\n"
        "• ціна/тариф\n"
        "• кнопка “Орендувати”\n\n"
        "Поки що — скелет ✅"
    )
    try:
        await cb.message.edit_text(txt, parse_mode="HTML", reply_markup=back_home_kb())
    except Exception:
        await cb.message.answer(txt, parse_mode="HTML", reply_markup=back_home_kb())
    await cb.answer()