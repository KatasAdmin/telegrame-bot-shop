# rent_platform/platform/handlers/start.py
from __future__ import annotations

import logging

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery

from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from rent_platform.platform.keyboards import (
    my_bots_kb,
    my_bots_list_kb,
    main_menu_kb,
    main_menu_inline_kb,
    back_to_menu_kb,
    partners_inline_kb,
    about_inline_kb,
    BTN_MARKETPLACE,
    BTN_MY_BOTS,
    BTN_CABINET,
    BTN_PARTNERS,
    BTN_HELP,
)
from rent_platform.platform.storage import list_bots, add_bot, delete_bot, pause_bot, resume_bot
)

log = logging.getLogger(__name__)
router = Router()


def _label(message: Message) -> str:
    chat_id = message.chat.id if message.chat else None
    user_id = message.from_user.id if message.from_user else None
    return f"chat={chat_id}, user={user_id}"


async def _send_main_menu(message: Message) -> None:
    text = (
        "✅ *Rent Platform запущено*\n\n"
        "Оберіть розділ:\n"
        "• 🧩 Маркетплейс — підключення модулів\n"
        "• 🤖 Мої боти — список орендованих/підключених\n"
        "• 👤 Кабінет — тариф, рахунки, статус\n"
        "• 🤝 Партнери — рефералка/виплати\n"
        "• 🆘 Підтримка — допомога\n"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=main_menu_kb(is_admin=False))
    await message.answer("Швидкі кнопки:", reply_markup=main_menu_inline_kb())


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    log.info("platform /start: %s", _label(message))
    await _send_main_menu(message)


# ===== Reply-кнопки (текст) =====

@router.message(F.text == BTN_MARKETPLACE)
async def marketplace_text(message: Message) -> None:
    await message.answer(
        "🧩 *Маркетплейс*\n\n"
        "Тут буде каталог модулів (shop / invest / …), підключення та керування.\n"
        "Поки що заглушка — далі зробимо список і «підключити».",
        parse_mode="Markdown",
        reply_markup=back_to_menu_kb(),
    )


@router.message(F.text == BTN_CABINET)
async def cabinet_text(message: Message) -> None:
    await message.answer(
        "👤 *Кабінет*\n\n"
        "Тут буде:\n"
        "• тариф і дата завершення\n"
        "• рахунок на оплату / історія оплат\n"
        "• баланс / бонуси (пізніше)\n\n"
        "Поки що заглушка 🙂",
        parse_mode="Markdown",
        reply_markup=back_to_menu_kb(),
    )


@router.message(F.text == BTN_PARTNERS)
async def partners_text(message: Message) -> None:
    await message.answer(
        "🤝 *Партнерська програма*\n\n"
        "Тут буде рефералка, статистика та виплати.\n"
        "Обери дію нижче 👇",
        parse_mode="Markdown",
        reply_markup=partners_inline_kb(),
    )


@router.message(F.text == BTN_HELP)
async def support_text(message: Message) -> None:
    await message.answer(
        "🆘 *Підтримка*\n\n"
        "Напиши, що не працює, і додай:\n"
        "• що натискав\n"
        "• скрін/лог (якщо є)\n\n"
        "Також є розділ «Загальна інформація» 👇",
        parse_mode="Markdown",
        reply_markup=about_inline_kb(),
    )


# ===== Callback (inline) =====

@router.callback_query(F.data == "pl:menu")
async def cb_menu(call: CallbackQuery) -> None:
    if call.message:
        await call.message.answer("⬇️ Меню", reply_markup=main_menu_kb(is_admin=False))
        await call.message.answer("Швидкі кнопки:", reply_markup=main_menu_inline_kb())
    await call.answer()


@router.callback_query(F.data == "pl:marketplace")
async def cb_marketplace(call: CallbackQuery) -> None:
    if call.message:
        await call.message.answer(
            "🧩 *Маркетплейс*\n\n(заглушка, далі зробимо список модулів)",
            parse_mode="Markdown",
            reply_markup=back_to_menu_kb(),
        )
    await call.answer()


@router.callback_query(F.data == "pl:cabinet")
async def cb_cabinet(call: CallbackQuery) -> None:
    if call.message:
        await call.message.answer(
            "👤 *Кабінет*\n\n(заглушка, далі — тариф/рахунки/оплата)",
            parse_mode="Markdown",
            reply_markup=back_to_menu_kb(),
        )
    await call.answer()


@router.callback_query(F.data == "pl:partners")
async def cb_partners(call: CallbackQuery) -> None:
    if call.message:
        await call.message.answer(
            "🤝 *Партнери*\n\nОбери дію 👇",
            parse_mode="Markdown",
            reply_markup=partners_inline_kb(),
        )
    await call.answer()


@router.callback_query(F.data == "pl:support")
async def cb_support(call: CallbackQuery) -> None:
    if call.message:
        await call.message.answer(
            "🆘 *Підтримка*\n\nТакож є «Загальна інформація» 👇",
            parse_mode="Markdown",
            reply_markup=about_inline_kb(),
        )
    await call.answer()


# --- Partners sub-callbacks (заглушки) ---

@router.callback_query(F.data.startswith("pl:partners:"))
async def cb_partners_sub(call: CallbackQuery) -> None:
    if not call.message:
        await call.answer()
        return

    key = call.data.split("pl:partners:", 1)[1]
    mapping = {
        "link": "🔗 *Моя реф-силка*\n\n(заглушка: далі згенеруємо рефкод і посилання)",
        "stats": "📊 *Статистика*\n\n(заглушка: реєстрації/оплати/комісія)",
        "payouts": "💸 *Виплати*\n\n(заглушка: реквізити/історія/статус)",
        "rules": "📜 *Правила*\n\n(заглушка: умови партнерки)",
    }
    await call.message.answer(
        mapping.get(key, "Пункт у розробці."),
        parse_mode="Markdown",
        reply_markup=partners_inline_kb(),
    )
    await call.answer()


# ===== My Bots =====

class MyBotsFlow(StatesGroup):
    waiting_token = State()


async def _render_my_bots(message: Message) -> None:
    user_id = message.from_user.id
    items = await list_bots(user_id)

    if not items:
        await message.answer(
            "🤖 *Мої боти*\n\n"
            "Поки порожньо.\n"
            "Натисни **➕ Додати бота** і встав токен.\n\n"
            "_Пізніше тут буде: статус оренди, модулі, конфігурація._",
            parse_mode="Markdown",
            reply_markup=my_bots_kb(),
        )
        return

    # короткий текст + окремо список керування
    await message.answer(
        "🤖 *Мої боти*\n\n"
        "Нижче — керування (пауза/відновити/видалити).",
        parse_mode="Markdown",
        reply_markup=my_bots_kb(),
    )
    await message.answer("⚙️ Керування ботами:", reply_markup=my_bots_list_kb(items))


@router.message(F.text == BTN_MY_BOTS)
async def my_bots_text(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _render_my_bots(message)


@router.callback_query(F.data == "pl:my_bots")
async def cb_my_bots(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if call.message:
        await _render_my_bots(call.message)
    await call.answer()


@router.callback_query(F.data == "pl:my_bots:refresh")
async def cb_my_bots_refresh(call: CallbackQuery, state: FSMContext) -> None:
    await cb_my_bots(call, state)


@router.callback_query(F.data == "pl:my_bots:add")
async def cb_my_bots_add(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(MyBotsFlow.waiting_token)
    if call.message:
        await call.message.answer(
            "➕ *Додати бота*\n\n"
            "Встав токен бота (формат як у BotFather: `123456:AA...`).\n\n"
            "❗️Не кидай токен у публічні чати.",
            parse_mode="Markdown",
        )
    await call.answer()


@router.message(MyBotsFlow.waiting_token, F.text)
async def my_bots_receive_token(message: Message, state: FSMContext) -> None:
    token = (message.text or "").strip()

    if ":" not in token or len(token) < 20:
        await message.answer("❌ Схоже на невалідний токен. Спробуй ще раз (має бути `числа:букви...`).")
        return

    user_id = message.from_user.id
    await add_bot(user_id, token=token, name="Bot")  # webhook ставиться всередині storage.add_bot

    await state.clear()
    await message.answer("✅ Додав. Тепер це буде твоїм “орендованим/підключеним ботом” у платформі.")
    await _render_my_bots(message)


# --- My bots actions ---

@router.callback_query(F.data.startswith("pl:my_bots:noop:"))
async def cb_my_bots_noop(call: CallbackQuery) -> None:
    await call.answer("🙂")


@router.callback_query(F.data.startswith("pl:my_bots:pause:"))
async def cb_my_bots_pause(call: CallbackQuery) -> None:
    bot_id = call.data.split("pl:my_bots:pause:", 1)[1]
    ok = await pause_bot(call.from_user.id, bot_id)
    if call.message:
        await call.message.answer("⏸ Поставив на паузу." if ok else "⚠️ Не вийшло (не знайдено/нема доступу).")
        await _render_my_bots(call.message)
    await call.answer()


@router.callback_query(F.data.startswith("pl:my_bots:resume:"))
async def cb_my_bots_resume(call: CallbackQuery) -> None:
    bot_id = call.data.split("pl:my_bots:resume:", 1)[1]
    ok = await resume_bot(call.from_user.id, bot_id)
    if call.message:
        await call.message.answer("▶️ Відновив." if ok else "⚠️ Не вийшло (не знайдено/нема доступу).")
        await _render_my_bots(call.message)
    await call.answer()


@router.callback_query(F.data.startswith("pl:my_bots:del:"))
async def cb_my_bots_delete(call: CallbackQuery) -> None:
    bot_id = call.data.split("pl:my_bots:del:", 1)[1]
    ok = await delete_bot(call.from_user.id, bot_id)
    if call.message:
        await call.message.answer("🗑 Видалив (soft) + webhook вимкнув." if ok else "⚠️ Не знайшов такого бота.")
        await _render_my_bots(call.message)
    await call.answer()