# rent_platform/platform/handlers/start.py
from __future__ import annotations

import logging
import time
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from rent_platform.platform.keyboards import (
    # menus
    main_menu_kb,
    main_menu_inline_kb,
    back_to_menu_kb,
    partners_inline_kb,
    about_inline_kb,
    # buttons (reply texts)
    BTN_MARKETPLACE,
    BTN_MY_BOTS,
    BTN_CABINET,
    BTN_PARTNERS,
    BTN_HELP,
    # my bots
    my_bots_kb,
    my_bots_list_kb,
    # marketplace
    marketplace_bots_kb,
    marketplace_modules_kb,
    # payments
    cabinet_pay_kb,
)

from rent_platform.platform.storage import (
    # my bots
    list_bots,
    add_bot,
    delete_bot,
    pause_bot,
    resume_bot,
    # marketplace
    list_bot_modules,
    enable_module,
    disable_module,
    # cabinet
    get_cabinet,
    # payments
    create_payment_link,
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


# ======================================================================
# Reply-кнопки (текст)
# ======================================================================

@router.message(F.text == BTN_MARKETPLACE)
async def marketplace_text(message: Message) -> None:
    await _render_marketplace_pick_bot(message)


@router.message(F.text == BTN_CABINET)
async def cabinet_text(message: Message) -> None:
    try:
        await _render_cabinet(message)
    except Exception as e:
        log.exception("cabinet failed: %s", e)
        await message.answer(
            "⚠️ Кабінет тимчасово впав. Я вже бачу помилку в логах 🙂",
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


# ======================================================================
# Callback (inline)
# ======================================================================

@router.callback_query(F.data == "pl:menu")
async def cb_menu(call: CallbackQuery) -> None:
    if call.message:
        await _send_main_menu(call.message)
    await call.answer()


@router.callback_query(F.data == "pl:marketplace")
async def cb_marketplace(call: CallbackQuery) -> None:
    if call.message:
        await _render_marketplace_pick_bot(call.message)
    await call.answer()


@router.callback_query(F.data == "pl:cabinet")
async def cb_cabinet(call: CallbackQuery) -> None:
    if call.message:
        try:
            await _render_cabinet(call.message)
        except Exception as e:
            log.exception("cb_cabinet failed: %s", e)
            await call.message.answer("⚠️ Кабінет тимчасово впав.", reply_markup=back_to_menu_kb())
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


# ======================================================================
# Кабінет
# ======================================================================

def _fmt_ts(ts: int) -> str:
    if not ts:
        return "—"
    return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M")


async def _render_cabinet(message: Message) -> None:
    user_id = message.from_user.id
    data = await get_cabinet(user_id)

    now = int(data.get("now") or time.time())
    bots = data.get("bots") or []

    if not bots:
        text = (
            "👤 Кабінет\n\n"
            "Поки що в тебе немає підключених ботів.\n"
            "Перейди в «Мої боти» і додай токен.\n\n"
            "Далі тут буде: тариф/оплата/рахунки/бонуси."
        )
        await message.answer(text, reply_markup=back_to_menu_kb())
        return

    lines = [
        "👤 Кабінет",
        "",
        f"🕒 Зараз: {_fmt_ts(now)}",
        "",
        "Твої боти і статуси:",
    ]

    expired_bots: list[str] = []

    for i, b in enumerate(bots, 1):
        st = (b.get("status") or "active").lower()
        plan = (b.get("plan_key") or "free")
        paid_until = int(b.get("paid_until_ts") or 0)
        expired = bool(b.get("expired"))
        paused_reason = b.get("paused_reason")

        badge = (
            "✅ active" if st == "active"
            else "⏸ paused" if st == "paused"
            else "🗑 deleted" if st == "deleted"
            else st
        )

        pay_str = _fmt_ts(paid_until)
        pay_note = " ⚠️ прострочено" if expired else ""
        extra = f" (reason: {paused_reason})" if paused_reason else ""

        lines.append(
            f"{i}) {b.get('name','Bot')} — {badge}{extra}\n"
            f"   • plan: {plan}\n"
            f"   • paid_until: {pay_str}{pay_note}\n"
            f"   • id: {b['id']}"
        )

        # ⬇️ збираємо прострочені — щоб показати кнопки оплати нижче окремими повідомленнями
        if expired and st != "deleted":
            expired_bots.append(b["id"])

    lines += [
        "",
        "Далі додамо: оплату/плани, авто-паузу при 0 балансі, рахунки та історію платежів.",
    ]

    # ❗️без parse_mode (щоб не ловити Markdown entity errors)
    await message.answer("\n".join(lines), reply_markup=back_to_menu_kb())

    # Окремими повідомленнями даємо оплату для кожного простроченого
    for bot_id in expired_bots:
        await message.answer(
            f"⚠️ Бот `{bot_id}` прострочений.\n"
            f"Щоб продовжити — натисни оплату 👇",
            parse_mode="Markdown",
            reply_markup=cabinet_pay_kb(bot_id),
        )


# ======================================================================
# Marketplace (модулі)
# ======================================================================

async def _render_marketplace_pick_bot(message: Message) -> None:
    user_id = message.from_user.id
    items = await list_bots(user_id)

    if not items:
        await message.answer(
            "🧩 *Маркетплейс*\n\n"
            "Спочатку додай хоча б одного бота в розділі **Мої боти**.\n"
            "Після цього тут зʼявиться керування модулями 🙂",
            parse_mode="Markdown",
            reply_markup=back_to_menu_kb(),
        )
        return

    await message.answer(
        "🧩 *Маркетплейс модулів*\n\n"
        "Обери бота, щоб підключати/вимикати модулі:",
        parse_mode="Markdown",
        reply_markup=marketplace_bots_kb(items),
    )


@router.callback_query(F.data.startswith("pl:mp:bot:"))
async def cb_marketplace_bot(call: CallbackQuery) -> None:
    if not call.message:
        await call.answer()
        return

    bot_id = call.data.split("pl:mp:bot:", 1)[1]
    user_id = call.from_user.id

    data = await list_bot_modules(user_id, bot_id)
    if not data:
        await call.message.answer("⚠️ Не знайшов бота або нема доступу.")
        await call.answer()
        return

    st = (data.get("status") or "active").lower()
    if st == "deleted":
        await call.message.answer("🗑 Цей бот видалений (soft). Керування модулями недоступне.")
        await call.answer()
        return

    modules = data["modules"]
    lines = [f"🧩 *Модулі для бота* `{bot_id}`", ""]
    for m in modules:
        lines.append(f"• {'✅' if m['enabled'] else '➕'} *{m['title']}* — {m['desc']}")

    if st == "paused":
        lines += ["", "⏸ Бот на паузі. Модулі можна налаштовувати, але апдейти не приходять, поки не відновиш."]

    await call.message.answer(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=marketplace_modules_kb(bot_id, modules),
    )
    await call.answer()


@router.callback_query(F.data.startswith("pl:mp:tg:"))
async def cb_marketplace_toggle(call: CallbackQuery) -> None:
    if not call.message:
        await call.answer()
        return

    payload = call.data.split("pl:mp:tg:", 1)[1]
    try:
        bot_id, module_key = payload.split(":", 1)
    except ValueError:
        await call.answer("⚠️ Bad payload")
        return

    user_id = call.from_user.id

    info = await list_bot_modules(user_id, bot_id)
    if not info:
        await call.message.answer("⚠️ Не знайшов бота або нема доступу.")
        await call.answer()
        return

    st = (info.get("status") or "active").lower()
    if st == "deleted":
        await call.answer("Бот видалений")
        return

    modules = info["modules"]
    current = next((m for m in modules if m["key"] == module_key), None)
    if not current:
        await call.answer("Невідомий модуль")
        return

    if current["enabled"]:
        ok = await disable_module(user_id, bot_id, module_key)
        if not ok:
            await call.answer("Не можна вимкнути", show_alert=True)
        else:
            await call.answer("Вимкнув ✅")
    else:
        ok = await enable_module(user_id, bot_id, module_key)
        if not ok:
            await call.answer("Не можна увімкнути", show_alert=True)
        else:
            await call.answer("Увімкнув ✅")

    # перерендеримо екран бота
    new_info = await list_bot_modules(user_id, bot_id)
    if new_info and call.message:
        new_modules = new_info["modules"]
        lines = [f"🧩 *Модулі для бота* `{bot_id}`", ""]
        for m in new_modules:
            lines.append(f"• {'✅' if m['enabled'] else '➕'} *{m['title']}* — {m['desc']}")
        if st == "paused":
            lines += ["", "⏸ Бот на паузі. Модулі можна налаштовувати."]

        await call.message.answer(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=marketplace_modules_kb(bot_id, new_modules),
        )
    await call.answer()


# ======================================================================
# Оплата (callback)
# ======================================================================

@router.callback_query(F.data.startswith("pl:pay:"))
async def cb_pay(call: CallbackQuery) -> None:
    if not call.message:
        await call.answer()
        return

    payload = call.data.split("pl:pay:", 1)[1]
    try:
        bot_id, months_s = payload.split(":", 1)
        months = int(months_s)
    except Exception:
        await call.answer("⚠️ Bad payload")
        return

    user_id = call.from_user.id
    invoice = await create_payment_link(user_id, bot_id, months=months)
    if not invoice:
        await call.answer("Нема доступу або не знайдено", show_alert=True)
        return

    await call.message.answer(
        f"💳 *Оплата*\n\n"
        f"Бот: `{bot_id}`\n"
        f"Період: *{months} міс*\n"
        f"Сума: *{invoice['amount_uah']} грн*\n\n"
        f"Посилання на оплату:\n{invoice['pay_url']}\n\n"
        f"_Після оплати бот автоматично оживе (auto-resume)._",
        parse_mode="Markdown",
        reply_markup=back_to_menu_kb(),
    )
    await call.answer("Створив інвойс ✅")


# ======================================================================
# My Bots
# ======================================================================

class MyBotsFlow(StatesGroup):
    waiting_token = State()


def _status_badge(st: str | None) -> str:
    st = (st or "active").lower()
    if st == "active":
        return "✅ active"
    if st == "paused":
        return "⏸ paused"
    if st == "deleted":
        return "🗑 deleted"
    return f"⚪️ {st}"


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

    lines = ["🤖 *Мої боти*"]
    for i, it in enumerate(items, 1):
        lines.append(f"{i}) **{it.get('name','Bot')}** — {_status_badge(it.get('status'))}  (id: `{it['id']}`)")

    await message.answer("\n".join(lines), parse_mode="Markdown", reply_markup=my_bots_kb())
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
    await add_bot(user_id, token=token, name="Bot")

    await state.clear()
    await message.answer("✅ Додав. Тепер це буде твоїм “орендованим/підключеним ботом” у платформі.")
    await _render_my_bots(message)


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