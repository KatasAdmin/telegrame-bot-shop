from __future__ import annotations

import datetime as _dt
import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.filters.command import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from rent_platform.db.repo import ReferralRepo
from rent_platform.platform.handlers.cabinet import register_cabinet, render_cabinet
from rent_platform.platform.keyboards import (
    # menus
    main_menu_kb,
    back_to_menu_kb,

    # info/partners
    partners_inline_kb,
    about_inline_kb,

    # marketplace
    marketplace_products_kb,
    marketplace_buy_kb,

    # config
    config_kb,

    # topup
    topup_provider_kb,
    topup_confirm_kb,

    # btn constants
    BTN_MARKETPLACE,
    BTN_MY_BOTS,
    BTN_CABINET,
    BTN_PARTNERS,
    BTN_HELP,
)

from rent_platform.platform.storage import (
    # my bots
    list_bots,
    add_bot,
    delete_bot,
    pause_bot,
    resume_bot,

    # marketplace
    list_marketplace_products,
    get_marketplace_product,
    buy_product,

    # partners
    partners_create_payout,

    # topup
    create_topup_invoice,
    confirm_topup_paid_test,

    # config
    get_bot_config,
    toggle_integration,
    set_bot_secret,
)

log = logging.getLogger(__name__)
router = Router()

# Реєструємо маршрути кабінету з окремого файлу
register_cabinet(router)

# ======================================================================
# MENU_TEXTS — що має “перебивати” будь-який FSM
# ======================================================================
MENU_TEXTS = {
    "⬅️ В меню",
    "В меню",
    "Меню",
    "/start",
    BTN_MARKETPLACE,
    BTN_MY_BOTS,
    BTN_CABINET,
    BTN_PARTNERS,
    BTN_HELP,
}


class MyBotsFlow(StatesGroup):
    waiting_token = State()


class ConfigFlow(StatesGroup):
    waiting_secret_value = State()


class MarketplaceBuyFlow(StatesGroup):
    waiting_bot_token = State()


class TopUpFlow(StatesGroup):
    waiting_amount = State()


class RefPayoutFlow(StatesGroup):
    waiting_amount = State()


def _md_escape(text: str) -> str:
    # Markdown (не V2)
    return (
        str(text)
        .replace("_", "\\_")
        .replace("*", "\\*")
        .replace("`", "\\`")
        .replace("[", "\\[")
    )


def _fmt_paid_until(ts: int | None) -> str:
    try:
        ts_i = int(ts or 0)
    except Exception:
        ts_i = 0
    if ts_i <= 0:
        return "—"
    return _dt.datetime.fromtimestamp(ts_i).strftime("%Y-%m-%d %H:%M")


def _status_badge(st: str | None, paused_reason: str | None = None) -> str:
    st = (st or "active").lower()
    pr = (paused_reason or "").lower()

    if st == "active":
        return "🟢 активний"
    if st == "paused":
        if pr == "billing":
            return "🔻 пауза • білінг"
        if pr == "manual":
            return "🟡 пауза • вручну"
        return "⏸ пауза"
    if st == "deleted":
        return "🗑 видалено"
    return f"⚪️ {st}"


async def _send_main_menu(message: Message) -> None:
    text = (
        "🚀 *Bot Shop — Rent Platform*\n"
        "_Маркетплейс ботів і модулів з оплатою з балансу._\n\n"
        "Обери розділ 👇\n\n"
        "🧩 *Маркетплейс* — обрати продукт і підключити токен\n"
        "🤖 *Мої боти* — список ботів + конфіг\n"
        "👤 *Кабінет* — баланс, тарифи, історія\n"
        "🤝 *Партнери* — рефералка, статистика, виплати\n"
        "🆘 *Підтримка* — правила, приватність, контакти\n"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=main_menu_kb(is_admin=False))


# ======================================================================
# ✅ Меню-кнопки працюють завжди, навіть у будь-якому FSM
# ======================================================================
@router.message(StateFilter("*"), F.text.in_(MENU_TEXTS))
async def menu_buttons_always_work(message: Message, state: FSMContext) -> None:
    await state.clear()

    if message.text == BTN_MARKETPLACE:
        await _render_marketplace(message)
        return

    if message.text == BTN_MY_BOTS:
        await _render_my_bots(message)
        return

    if message.text == BTN_CABINET:
        try:
            await render_cabinet(message)
        except Exception as e:
            log.exception("cabinet failed: %s", e)
            await message.answer("⚠️ Кабінет тимчасово недоступний.", reply_markup=back_to_menu_kb())
        return

    if message.text == BTN_PARTNERS:
        await partners_text(message, state)
        return

    if message.text == BTN_HELP:
        await support_text(message, state)
        return

    await _send_main_menu(message)


@router.message(Command("menu"))
@router.message(F.text.in_(["⬅️ В меню", "В меню", "Меню"]))
async def back_to_menu_text(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _send_main_menu(message)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject) -> None:
    await state.clear()

    user_id = message.from_user.id
    payload = (command.args or "").strip()  # ref_123456
    if payload.startswith("ref_"):
        try:
            referrer_id = int(payload.split("ref_", 1)[1])
            await ReferralRepo.bind(user_id=user_id, referrer_id=referrer_id)
        except Exception:
            pass

    await _send_main_menu(message)


# ======================================================================
# Partners / Support helpers
# ======================================================================
async def partners_text(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "🤝 *Партнерська програма*\n\n"
        "Запроси друзів — і отримуй % з їх поповнень та списань.\n\n"
        "Доступно зараз:\n"
        "• 🔗 реф-силка\n"
        "• 📊 статистика\n"
        "• 💸 виплати (заявка)\n"
        "• 📜 правила\n",
        parse_mode="Markdown",
        reply_markup=partners_inline_kb(),
    )


async def support_text(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "🆘 *Підтримка*\n\n"
        "Тут зібрані правила та важлива інформація про сервіс.\n"
        "Обери пункт 👇",
        parse_mode="Markdown",
        reply_markup=about_inline_kb(),
    )


# ======================================================================
# Inline: global menu
# ======================================================================
@router.callback_query(F.data == "pl:menu")
async def cb_menu(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if call.message:
        await _send_main_menu(call.message)
    await call.answer()


@router.callback_query(F.data == "pl:marketplace")
async def cb_marketplace(call: CallbackQuery) -> None:
    if call.message:
        await _render_marketplace(call.message)
    await call.answer()


@router.callback_query(F.data == "pl:my_bots")
async def cb_my_bots(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if call.message:
        await _render_my_bots(call.message)
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
            "🆘 *Підтримка*\n\nОбери пункт 👇",
            parse_mode="Markdown",
            reply_markup=about_inline_kb(),
        )
    await call.answer()


@router.callback_query(F.data == "pl:about")
async def cb_about(call: CallbackQuery) -> None:
    if call.message:
        await call.message.answer(
            "ℹ️ *Про платформу*\n\n"
            "*Bot Shop (Rent Platform)* — оренда ботів/модулів.\n\n"
            "Як це працює:\n"
            "1) Обираєш продукт у маркетплейсі\n"
            "2) Вставляєш токен (BotFather)\n"
            "3) Бот запускається, а оплата йде з балансу\n\n"
            "✅ Статус: MVP працює\n"
            "_Далі додамо адмінку, реальні оплати та більше статистики._",
            parse_mode="Markdown",
            reply_markup=back_to_menu_kb(),
        )
    await call.answer()


@router.callback_query(F.data == "pl:privacy")
async def cb_privacy(call: CallbackQuery) -> None:
    if call.message:
        await call.message.answer(
            "🔒 *Конфіденційність*\n\n"
            "• Токени використовуються лише для роботи оренди.\n"
            "• Не публікуй токени у чатах.\n"
            "• Дані потрібні тільки для надання сервісу.\n\n"
            "_Згодом винесемо в окремий документ (URL)._",
            parse_mode="Markdown",
            reply_markup=back_to_menu_kb(),
        )
    await call.answer()


@router.callback_query(F.data == "pl:terms")
async def cb_terms(call: CallbackQuery) -> None:
    if call.message:
        await call.message.answer(
            "📄 *Умови користування*\n\n"
            "• Ти відповідаєш за контент і дії свого бота.\n"
            "• Ми даємо технічну оренду модулів/інфраструктури.\n"
            "• При нульовому балансі бот може бути на паузі.\n\n"
            "_Далі буде повний документ._",
            parse_mode="Markdown",
            reply_markup=back_to_menu_kb(),
        )
    await call.answer()


@router.callback_query(F.data == "pl:commitments")
async def cb_commitments(call: CallbackQuery) -> None:
    if call.message:
        await call.message.answer(
            "🛡 *Наші принципи*\n\n"
            "• Мінімум доступів — тільки необхідне.\n"
            "• Прозорі списання — все видно в історії (ledger).\n"
            "• Контроль — пауза/відновлення у 2 кліки.\n\n"
            "План розвитку:\n"
            "• адмінка\n"
            "• реальні оплати (mono/privat/crypto)\n"
            "• глибша статистика\n",
            parse_mode="Markdown",
            reply_markup=back_to_menu_kb(),
        )
    await call.answer()


# ======================================================================
# Partners callbacks
# ======================================================================
@router.callback_query(F.data == "pl:partners:payout_create")
async def cb_ref_payout_create(call: CallbackQuery, state: FSMContext) -> None:
    if not call.message:
        await call.answer()
        return

    await state.set_state(RefPayoutFlow.waiting_amount)

    s = await ReferralRepo.get_settings()
    min_payout = int(s.get("min_payout_kop") or 0) / 100

    await call.message.answer(
        "➕ *Заявка на виплату*\n\n"
        f"Введи суму в грн (мінімум *{min_payout:.2f}*).\n"
        "Напр: `250`\n\n"
        "_Скасувати можна через «В меню»_",
        parse_mode="Markdown",
        reply_markup=partners_inline_kb(),
    )
    await call.answer()


@router.message(RefPayoutFlow.waiting_amount, F.text, ~F.text.in_(MENU_TEXTS))
async def ref_payout_receive_amount(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip().replace(",", ".").replace(" ", "")

    try:
        uah = float(raw)
        if uah <= 0:
            raise ValueError
    except Exception:
        await message.answer("❌ Введи число в грн, напр `250`", parse_mode="Markdown", reply_markup=partners_inline_kb())
        return

    s = await ReferralRepo.get_settings()
    min_payout = int(s.get("min_payout_kop") or 0) / 100
    if uah < min_payout:
        await message.answer(
            f"❌ Мінімальна виплата: *{min_payout:.2f} грн*",
            parse_mode="Markdown",
            reply_markup=partners_inline_kb(),
        )
        return

    amount_kop = int(round(uah * 100))
    await state.clear()

    req = await partners_create_payout(message.from_user.id, amount_kop=amount_kop, note="tg_bot")
    if not req:
        await message.answer(
            "⚠️ Не вийшло створити заявку.\n\n"
            "Перевір: достатній доступний баланс і мінімальну суму.",
            reply_markup=partners_inline_kb(),
        )
        return

    await message.answer(
        "✅ *Заявку створено!*\n\n"
        f"ID: `#{req['id']}`\n"
        f"Сума: *{int(req['amount_kop'])/100:.2f} грн*\n"
        "Статус: *pending*\n\n"
        "_Адмін підтвердить виплату — і статус зміниться._",
        parse_mode="Markdown",
        reply_markup=partners_inline_kb(),
    )


@router.callback_query(F.data.startswith("pl:partners:"))
async def cb_partners_sub(call: CallbackQuery) -> None:
    if not call.message:
        await call.answer()
        return

    key = call.data.split("pl:partners:", 1)[1]
    me = await call.bot.get_me()
    bot_username = me.username or ""

    if key == "link":
        if not bot_username:
            await call.message.answer("⚠️ Не зміг отримати username бота.")
            await call.answer()
            return
        ref_link = f"https://t.me/{bot_username}?start=ref_{call.from_user.id}"
        await call.message.answer(
            "🔗 *Твоя реф-силка*\n\n"
            "Надсилай друзям. Коли вони почнуть користуватись платформою — "
            "ти отримуватимеш партнерські %.\n\n"
            f"`{ref_link}`",
            parse_mode="Markdown",
            reply_markup=partners_inline_kb(),
        )
        await call.answer()
        return

    if key == "stats":
        try:
            st = await ReferralRepo.stats(call.from_user.id)
            refs_cnt = int(st.get("refs_cnt") or 0)
            available = int(st.get("available_kop") or 0) / 100
            earned = int(st.get("total_earned_kop") or 0) / 100
            paid = int(st.get("total_paid_kop") or 0) / 100

            by_kind = st.get("by_kind") or {}
            topup_s = int(by_kind.get("topup") or 0) / 100
            billing_s = int(by_kind.get("billing") or 0) / 100

            await call.message.answer(
                "📊 *Статистика партнера*\n\n"
                f"👥 Рефералів: *{refs_cnt}*\n"
                f"💰 Доступно: *{available:.2f} грн*\n"
                f"🏆 Зароблено всього: *{earned:.2f} грн*\n"
                f"💸 Виплачено: *{paid:.2f} грн*\n\n"
                "Джерела:\n"
                f"• з поповнень: *{topup_s:.2f} грн*\n"
                f"• з білінгу: *{billing_s:.2f} грн*",
                parse_mode="Markdown",
                reply_markup=partners_inline_kb(),
            )
        except Exception:
            await call.message.answer("⚠️ Не зміг завантажити статистику.", reply_markup=partners_inline_kb())
        await call.answer()
        return

    if key == "payouts":
        settings = await ReferralRepo.get_settings()
        min_payout = int(settings.get("min_payout_kop") or 0) / 100
        bal = await ReferralRepo.get_balance(call.from_user.id) or {}
        available = int(bal.get("available_kop") or 0) / 100

        await call.message.answer(
            "💸 *Виплати*\n\n"
            f"Доступно: *{available:.2f} грн*\n"
            f"Мін. виплата: *{min_payout:.2f} грн*\n\n"
            "Натисни «➕ Заявка на виплату» — і введи суму.",
            parse_mode="Markdown",
            reply_markup=partners_inline_kb(),
        )
        await call.answer()
        return

    if key == "rules":
        s = await ReferralRepo.get_settings()
        pct_topup = int(s.get("percent_topup_bps") or 0) / 100
        pct_billing = int(s.get("percent_billing_bps") or 0) / 100
        min_payout = int(s.get("min_payout_kop") or 0) / 100

        await call.message.answer(
            "📜 *Правила партнерської програми*\n\n"
            f"• З поповнень рефералів: *{pct_topup:.2f}%*\n"
            f"• З білінгу (списань): *{pct_billing:.2f}%*\n"
            f"• Мінімальна виплата: *{min_payout:.2f} грн*\n\n"
            "Умови:\n"
            "1) Реферал зараховується, якщо зайшов по твоєму старт-лінку.\n"
            "2) Нарахування йдуть автоматично та прозоро (ledger).\n"
            "3) При накрутці/спамі — можемо обнулити бонуси.\n\n"
            "Порада: кидай реф-силку тим, хто реально буде запускати бота/оренду 🙂",
            parse_mode="Markdown",
            reply_markup=partners_inline_kb(),
        )
        await call.answer()
        return

    await call.message.answer("Пункт у розробці.", reply_markup=partners_inline_kb())
    await call.answer()


# ======================================================================
# Marketplace
# ======================================================================
def _rate_text(p: dict) -> str:
    kop = p.get("rate_per_min_kop")
    if kop is not None:
        try:
            return f"{int(kop) / 100:.2f} грн/хв"
        except Exception:
            pass
    try:
        return f"{float(p.get('rate_per_min_uah', 0)):.2f} грн/хв"
    except Exception:
        return f"{p.get('rate_per_min_uah', 0)} грн/хв"


async def _render_marketplace(message: Message) -> None:
    items = await list_marketplace_products()

    if not items:
        await message.answer(
            "🧩 *Маркетплейс*\n\nПоки що немає продуктів 🙂",
            parse_mode="Markdown",
            reply_markup=back_to_menu_kb(),
        )
        return

    lines = ["🧩 *Маркетплейс ботів*", "", "Обери продукт 👇", ""]
    for it in items:
        title = it.get("title") or it.get("key")
        short = (it.get("short") or "").strip()
        rate = _rate_text(it)

        lines.append(f"• *{_md_escape(title)}*")
        if short:
            lines.append(f"  _{_md_escape(short)}_")
        if rate and rate not in ("0 грн/хв", "0.00 грн/хв"):
            lines.append(f"  ⏱ *{rate}*")
        lines.append("")

    await message.answer(
        "\n".join(lines).strip(),
        parse_mode="Markdown",
        reply_markup=marketplace_products_kb(items),
    )


@router.callback_query(F.data.startswith("pl:mkp:open:"))
async def cb_mkp_open(call: CallbackQuery) -> None:
    if not call.message:
        await call.answer()
        return

    product_key = call.data.split("pl:mkp:open:", 1)[1]
    p = await get_marketplace_product(product_key)
    if not p:
        await call.answer("Не знайдено", show_alert=True)
        return

    title = p.get("title") or "Продукт"
    desc = p.get("desc") or ""

    text = (
        "🧩 *Продукт*\n\n"
        f"*{_md_escape(title)}*\n"
        f"{_md_escape(desc)}\n\n"
        f"⏱ *Тариф:* `{_rate_text(p)}`\n\n"
        "Натисни «Купити» — я попрошу токен (BotFather), щоб створити твою копію."
    )

    await call.message.answer(text, parse_mode="Markdown", reply_markup=marketplace_buy_kb(product_key))
    await call.answer()


@router.callback_query(F.data.startswith("pl:mkp:buy:"))
async def cb_mkp_buy(call: CallbackQuery, state: FSMContext) -> None:
    if not call.message:
        await call.answer()
        return

    product_key = call.data.split("pl:mkp:buy:", 1)[1]
    p = await buy_product(call.from_user.id, product_key)
    if not p:
        await call.answer("Не знайдено", show_alert=True)
        return

    await state.set_state(MarketplaceBuyFlow.waiting_bot_token)
    await state.update_data(mkp_product_key=product_key)

    await call.message.answer(
        "✅ *Покупка: створення твоєї копії*\n\n"
        "Встав *BotFather токен* бота, який буде працювати як твоя копія.\n"
        "Формат: `123456:AA...`\n\n"
        "⚠️ Не кидай токен у публічні чати.",
        parse_mode="Markdown",
        reply_markup=back_to_menu_kb(),
    )
    await call.answer("Ок")


@router.message(MarketplaceBuyFlow.waiting_bot_token, F.text, ~F.text.in_(MENU_TEXTS))
async def mkp_receive_token(message: Message, state: FSMContext) -> None:
    token = (message.text or "").strip()
    data = await state.get_data()
    product_key = data.get("mkp_product_key")

    if not product_key:
        await state.clear()
        await message.answer(
            "⚠️ Стан покупки загубився.\n\nЗайди в Маркетплейс і натисни «Купити» ще раз.",
            reply_markup=back_to_menu_kb(),
        )
        return

    if ":" not in token or len(token) < 20:
        await message.answer("❌ Схоже на невалідний токен. Спробуй ще раз.")
        return

    p = await get_marketplace_product(product_key)
    nice_name = (p.get("title") if p else f"Продукт: {product_key}") or "Bot"

    tenant = await add_bot(
        message.from_user.id,
        token=token,
        name=nice_name,
        product_key=product_key,
    )

    await state.clear()

    await message.answer(
        "✅ *Готово! Твоя копія створена.*\n\n"
        f"ID: `{tenant['id']}`\n"
        f"Продукт: `{product_key}`\n\n"
        "Далі: «Мої боти» → обери бота → ⚙️ «Конфіг».",
        parse_mode="Markdown",
        reply_markup=back_to_menu_kb(),
    )


# ======================================================================
# My Bots — дуже просто: список кнопок з ботами -> деталі -> конфіг
# ======================================================================
def _my_bots_list_buttons(items: list[dict], show_deleted: bool = False) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()

    visible = []
    deleted = []
    for it in items:
        st = (it.get("status") or "active").lower()
        if st == "deleted":
            deleted.append(it)
        else:
            visible.append(it)

    # список активних/paused
    for it in visible:
        bot_id = str(it["id"])
        name = (it.get("name") or "Bot").strip()
        st = (it.get("status") or "active").lower()
        icon = "🟢" if st == "active" else ("⏸" if st == "paused" else "⚪️")
        kb.button(text=f"{icon} {name}", callback_data=f"pl:my_bot:open:{bot_id}")

    # кнопка показу видалених
    if deleted and not show_deleted:
        kb.button(text=f"🗑 Показати видалені ({len(deleted)})", callback_data="pl:my_bots:deleted")

    kb.button(text="⬅️ В меню", callback_data="pl:menu")
    kb.adjust(1)
    return kb


def _my_bot_detail_kb(bot_id: str, status: str) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()

    if status == "deleted":
        kb.button(text="⬅️ Назад до списку", callback_data="pl:my_bots")
        kb.adjust(1)
        return kb

    kb.button(text="⚙️ Конфіг", callback_data=f"pl:cfg:open:{bot_id}")

    if status == "active":
        kb.button(text="⏸ Пауза", callback_data=f"pl:my_bot:pause:{bot_id}")
    elif status == "paused":
        kb.button(text="▶️ Відновити", callback_data=f"pl:my_bot:resume:{bot_id}")

    kb.button(text="🗑 Видалити", callback_data=f"pl:my_bot:del:{bot_id}")
    kb.button(text="⬅️ Назад до списку", callback_data="pl:my_bots")
    kb.adjust(1)
    return kb


async def _render_my_bots(message: Message) -> None:
    user_id = message.from_user.id
    items = await list_bots(user_id)

    if not items:
        await message.answer(
            "🤖 *Мої боти*\n\n"
            "Поки порожньо.\n"
            "Натисни *➕ Додати бота* і встав токен.",
            parse_mode="Markdown",
            reply_markup=_my_bots_list_buttons([]).as_markup(),
        )
        return

    await message.answer(
        "🤖 *Мої боти*\n\n"
        "Обери бота 👇",
        parse_mode="Markdown",
        reply_markup=_my_bots_list_buttons(items).as_markup(),
    )


@router.callback_query(F.data == "pl:my_bot:add")
async def cb_my_bots_add(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(MyBotsFlow.waiting_token)
    if call.message:
        await call.message.answer(
            "➕ *Додати бота*\n\nВстав токен (BotFather: `123456:AA...`).",
            parse_mode="Markdown",
            reply_markup=back_to_menu_kb(),
        )
    await call.answer()


@router.callback_query(F.data == "pl:my_bots:deleted")
async def cb_my_bots_deleted(call: CallbackQuery) -> None:
    if not call.message:
        await call.answer()
        return

    items = await list_bots(call.from_user.id)
    deleted = [x for x in items if (x.get("status") or "").lower() == "deleted"]

    if not deleted:
        await call.message.answer("🗑 Видалених ботів немає.")
        await call.answer()
        return

    kb = InlineKeyboardBuilder()
    for it in deleted:
        bot_id = str(it["id"])
        name = (it.get("name") or "Bot").strip()
        kb.button(text=f"🗑 {name}", callback_data=f"pl:my_bot:open:{bot_id}")
    kb.button(text="⬅️ Назад", callback_data="pl:my_bots")
    kb.adjust(1)

    await call.message.answer(
        "🗑 *Видалені боти*\n\nОбери бота (для перегляду інформації):",
        parse_mode="Markdown",
        reply_markup=kb.as_markup(),
    )
    await call.answer()


@router.message(MyBotsFlow.waiting_token, F.text, ~F.text.in_(MENU_TEXTS))
async def my_bots_receive_token(message: Message, state: FSMContext) -> None:
    token = (message.text or "").strip()

    if ":" not in token or len(token) < 20:
        await message.answer("❌ Схоже на невалідний токен. Спробуй ще раз.")
        return

    user_id = message.from_user.id
    await add_bot(user_id, token=token, name="Бот")

    await state.clear()
    await message.answer("✅ Додав. Відкриваю список…", reply_markup=back_to_menu_kb())
    await _render_my_bots(message)


@router.callback_query(F.data.startswith("pl:my_bot:open:"))
async def cb_my_bot_open(call: CallbackQuery) -> None:
    if not call.message:
        await call.answer()
        return

    bot_id = call.data.split("pl:my_bot:open:", 1)[1]
    items = await list_bots(call.from_user.id)
    it = next((x for x in items if str(x.get("id")) == str(bot_id)), None)
    if not it:
        await call.answer("Не знайдено", show_alert=True)
        return

    name = it.get("name") or "Bot"
    st = (it.get("status") or "active").lower()
    pr = it.get("paused_reason")
    pk = (it.get("product_key") or "—")
    plan = (it.get("plan_key") or "free")
    paid_until = _fmt_paid_until(it.get("paid_until_ts"))

    text = (
        "🤖 *Бот*\n\n"
        f"*{_md_escape(name)}*\n"
        f"Статус: {_status_badge(st, pr)}\n"
        f"ID: `{bot_id}`\n\n"
        f"🧩 Продукт: `{pk}`\n"
        f"📦 План: `{plan}`\n"
        f"⏳ Оплачено до: `{paid_until}`\n\n"
        "Керування 👇"
    )

    await call.message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=_my_bot_detail_kb(bot_id, st).as_markup(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("pl:my_bot:pause:"))
async def cb_my_bot_pause(call: CallbackQuery) -> None:
    bot_id = call.data.split("pl:my_bot:pause:", 1)[1]
    ok = await pause_bot(call.from_user.id, bot_id)
    if call.message:
        await call.message.answer("⏸ Поставив на паузу." if ok else "⚠️ Не вийшло.")
    await call.answer()


@router.callback_query(F.data.startswith("pl:my_bot:resume:"))
async def cb_my_bot_resume(call: CallbackQuery) -> None:
    bot_id = call.data.split("pl:my_bot:resume:", 1)[1]
    ok = await resume_bot(call.from_user.id, bot_id)
    if call.message:
        await call.message.answer("▶️ Відновив." if ok else "⚠️ Не вийшло.")
    await call.answer()


@router.callback_query(F.data.startswith("pl:my_bot:del:"))
async def cb_my_bot_delete(call: CallbackQuery) -> None:
    bot_id = call.data.split("pl:my_bot:del:", 1)[1]
    ok = await delete_bot(call.from_user.id, bot_id)
    if call.message:
        await call.message.answer("🗑 Видалив (soft)." if ok else "⚠️ Не знайшов такого бота.")
    await call.answer()


# ======================================================================
# Config (tenant keys)
# ======================================================================
async def _render_config(user_id: int, message: Message, bot_id: str) -> None:
    # ВАЖЛИВО: user_id беремо з call.from_user.id, а не з message.from_user.id
    data = await get_bot_config(user_id, bot_id)
    if not data:
        await message.answer("⚠️ Не знайшов бота або нема доступу.", reply_markup=back_to_menu_kb())
        return

    providers = data["providers"]

    lines = [f"⚙️ *Конфіг* `{bot_id}`", ""]
    for p in providers:
        lines.append(f"{'✅' if p['enabled'] else '➕'} *{p['title']}*")
        for s in p.get("secrets") or []:
            lines.append(f"   • `{s['key']}` = {s['value_masked']}")
        lines.append("")

    await message.answer(
        "\n".join(lines).strip(),
        parse_mode="Markdown",
        reply_markup=config_kb(bot_id, providers),
    )


@router.callback_query(F.data.startswith("pl:cfg:open:"))
async def cb_cfg_open(call: CallbackQuery) -> None:
    if call.message:
        bot_id = call.data.split("pl:cfg:open:", 1)[1]
        await _render_config(call.from_user.id, call.message, bot_id)
    await call.answer()


@router.callback_query(F.data.startswith("pl:cfg:tg:"))
async def cb_cfg_toggle(call: CallbackQuery) -> None:
    if not call.message:
        await call.answer()
        return

    payload = call.data.split("pl:cfg:tg:", 1)[1]
    try:
        bot_id, provider = payload.split(":", 1)
    except ValueError:
        await call.answer("⚠️ Bad payload")
        return

    ok = await toggle_integration(call.from_user.id, bot_id, provider)
    await call.answer("Ок ✅" if ok else "Не можна", show_alert=not ok)

    if ok:
        await _render_config(call.from_user.id, call.message, bot_id)


@router.callback_query(F.data.startswith("pl:cfg:set:"))
async def cb_cfg_set(call: CallbackQuery, state: FSMContext) -> None:
    if not call.message:
        await call.answer()
        return

    payload = call.data.split("pl:cfg:set:", 1)[1]
    try:
        bot_id, secret_key = payload.split(":", 1)
    except ValueError:
        await call.answer("⚠️ Bad payload")
        return

    await state.set_state(ConfigFlow.waiting_secret_value)
    await state.update_data(cfg_bot_id=bot_id, cfg_secret_key=secret_key)

    await call.message.answer(
        f"🔑 Встав значення для `{secret_key}`.\n\n"
        "⚠️ Не кидай це в публічні чати.",
        parse_mode="Markdown",
        reply_markup=back_to_menu_kb(),
    )
    await call.answer()


@router.message(ConfigFlow.waiting_secret_value, F.text)
async def cfg_receive_secret(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    bot_id = data.get("cfg_bot_id")
    secret_key = data.get("cfg_secret_key")
    value = (message.text or "").strip()

    if not bot_id or not secret_key:
        await state.clear()
        await message.answer("⚠️ Стан зламався, спробуй ще раз.", reply_markup=back_to_menu_kb())
        return

    ok = await set_bot_secret(message.from_user.id, bot_id, secret_key, value)
    await state.clear()

    if not ok:
        await message.answer(
            "⚠️ Не вийшло зберегти (нема доступу або ключ не дозволений).",
            reply_markup=back_to_menu_kb(),
        )
        return

    await message.answer("✅ Зберіг.", reply_markup=back_to_menu_kb())
    await _render_config(message.from_user.id, message, bot_id)

# ======================================================================
# TopUp (баланс) — MVP
# ======================================================================
@router.callback_query(F.data == "pl:topup:start")
async def cb_topup_start(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TopUpFlow.waiting_amount)
    if call.message:
        await call.message.answer(
            "💰 *Поповнення балансу*\n\n"
            "Введи суму в гривнях (цілим числом), напр: `200`",
            parse_mode="Markdown",
            reply_markup=back_to_menu_kb(),
        )
    await call.answer()


@router.message(TopUpFlow.waiting_amount, F.text, ~F.text.in_(MENU_TEXTS))
async def topup_receive_amount(message: Message, state: FSMContext) -> None:
    txt = (message.text or "").strip()
    raw = txt.replace(" ", "")
    if not raw.isdigit():
        await message.answer("❌ Введи число в грн, напр. 200")
        return

    amount = int(raw)
    if amount < 10:
        await message.answer("❌ Мінімум 10 грн. Спробуй ще раз.")
        return
    if amount > 200000:
        await message.answer("❌ Забагато 😄 Введи меншу суму.")
        return

    await state.clear()
    await message.answer(
        f"Обери спосіб поповнення на *{amount} грн* 👇",
        parse_mode="Markdown",
        reply_markup=topup_provider_kb(amount),
    )


@router.callback_query(F.data.startswith("pl:topup:prov:"))
async def cb_topup_provider(call: CallbackQuery) -> None:
    if not call.message:
        await call.answer()
        return

    payload = call.data.split("pl:topup:prov:", 1)[1]
    try:
        provider, amount_s = payload.split(":", 1)
        amount = int(amount_s)
    except Exception:
        await call.answer("⚠️ Bad payload")
        return

    inv = await create_topup_invoice(call.from_user.id, amount_uah=amount, provider=provider)
    if not inv:
        await call.answer("Не вийшло створити інвойс", show_alert=True)
        return

    await call.message.answer(
        "💳 *Інвойс створено*\n\n"
        f"Сума: *{inv['amount_uah']} грн*\n"
        f"Провайдер: *{provider}*\n\n"
        f"Посилання (поки заглушка):\n{inv['pay_url']}\n\n"
        "Для MVP натисни кнопку нижче (тестове підтвердження):",
        parse_mode="Markdown",
        reply_markup=topup_confirm_kb(int(inv["invoice_id"])),
    )
    await call.answer("OK")


@router.callback_query(F.data.startswith("pl:topup:confirm:"))
async def cb_topup_confirm(call: CallbackQuery) -> None:
    if not call.message:
        await call.answer()
        return

    invoice_id_s = call.data.split("pl:topup:confirm:", 1)[1]
    try:
        invoice_id = int(invoice_id_s)
    except Exception:
        await call.answer("⚠️ Bad invoice id")
        return

    res = await confirm_topup_paid_test(call.from_user.id, invoice_id)
    if not res:
        await call.answer("Не знайдено інвойс", show_alert=True)
        return

    # навіть якщо already=True — ми могли auto-resume зробити
    resumed_cnt = int(res.get("resumed_cnt") or 0)

    if res.get("already"):
        new_balance = int(res.get("new_balance_kop") or 0) / 100.0
        msg = (
            "ℹ️ Інвойс вже підтверджений або не pending.\n"
            f"💰 Баланс: {new_balance:.2f} грн"
        )
        if resumed_cnt > 0:
            msg += f"\n✅ Підняв ботів з білінг-паузи: {resumed_cnt}"
        await call.message.answer(msg, reply_markup=back_to_menu_kb())
        await call.answer()
        return

    new_balance = int(res["new_balance_kop"]) / 100.0
    added = int(res["amount_kop"]) / 100.0

    msg = (
        f"✅ Оплату підтверджено (тест). Баланс +{added:.2f} грн.\n"
        f"💰 Новий баланс: {new_balance:.2f} грн"
    )
    if resumed_cnt > 0:
        msg += f"\n✅ Підняв ботів з білінг-паузи: {resumed_cnt}"

    await call.message.answer(msg, reply_markup=back_to_menu_kb())
    await call.answer("✅")

# ======================================================================
# Debug fallback
# ======================================================================
from rent_platform.config import settings

def _is_admin(user_id: int) -> bool:
    # Підтримка різних варіантів, щоб не паритись:
    # ADMIN_USER_IDS="1,2,3" або ADMIN_ID="1"
    ids = []

    v = getattr(settings, "ADMIN_USER_IDS", None)
    if v:
        if isinstance(v, (list, tuple, set)):
            ids = [int(x) for x in v]
        else:
            # якщо раптом рядок "1,2,3"
            ids = [int(x.strip()) for x in str(v).split(",") if x.strip().isdigit()]

    one = getattr(settings, "ADMIN_ID", None)
    if one:
        try:
            ids.append(int(one))
        except Exception:
            pass

    return int(user_id) in set(ids)


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    await state.clear()

    if not _is_admin(message.from_user.id):
        await message.answer("⛔ Нема доступу.")
        return

    await message.answer(
        "⚙️ *Адмін-панель (MVP)*\n\n"
        "Обери дію 👇\n"
        "• 🤝 Партнерка: % / мін. виплата\n"
        "• 🧩 Продукти маркетплейсу\n"
        "• 📢 Банер кабінету\n"
        "• 💸 Підтвердження виплат (скоро)\n",
        parse_mode="Markdown",
        reply_markup=back_to_menu_kb(),
    )


@router.message(F.text, ~F.text.startswith("/"))
async def _debug_unhandled_text(message: Message, state: FSMContext) -> None:
    st = await state.get_state()
    if st:
        return
    log.warning(
        "UNHANDLED TEXT: %r | chat=%s user=%s",
        message.text,
        getattr(getattr(message, "chat", None), "id", None),
        getattr(getattr(message, "from_user", None), "id", None),
    )
    await message.answer("Не зрозумів 🙂 Натисни «Меню» або /start")