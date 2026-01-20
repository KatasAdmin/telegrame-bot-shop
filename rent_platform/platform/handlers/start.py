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
    # my bots
    my_bots_kb,
    my_bots_list_kb,

    # menus
    main_menu_kb,
    main_menu_inline_kb,
    back_to_menu_kb,

    # info/partners
    partners_inline_kb,
    about_inline_kb,

    # marketplace
    marketplace_products_kb,
    marketplace_buy_kb,

    # cabinet old pay (можеш лишити, навіть якщо не юзаєш зараз)
    cabinet_pay_kb,

    # config
    config_kb,

    # topup
    cabinet_topup_kb,
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

    # cabinet
    get_cabinet,
    create_payment_link,

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


class MyBotsFlow(StatesGroup):
    waiting_token = State()


class ConfigFlow(StatesGroup):
    waiting_secret_value = State()


class MarketplaceBuyFlow(StatesGroup):
    waiting_bot_token = State()

class TopUpFlow(StatesGroup):
    waiting_amount = State()

def _label(message: Message) -> str:
    chat_id = message.chat.id if message.chat else None
    user_id = message.from_user.id if message.from_user else None
    return f"chat={chat_id}, user={user_id}"


async def _send_main_menu(message: Message) -> None:
    text = (
        "✅ *Rent Platform запущено*\n\n"
        "Оберіть розділ:\n"
        "• 🧩 Маркетплейс — вибір продукту/оренда\n"
        "• 🤖 Мої боти — список підключених ботів\n"
        "• 👤 Кабінет — баланс / списання / статуси\n"
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
async def marketplace_text(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _render_marketplace_pick_bot(message)


@router.message(F.text == BTN_CABINET)
async def cabinet_text(message: Message) -> None:
    try:
        await _render_cabinet(message)
    except Exception as e:
        log.exception("cabinet failed: %s", e)
        await message.answer("⚠️ Кабінет тимчасово впав.", reply_markup=back_to_menu_kb())


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


@router.message(F.text == BTN_MY_BOTS)
async def my_bots_text(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _render_my_bots(message)


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

def _rate_text(p: dict) -> str:
    # пріоритет: kop -> uah
    kop = p.get("rate_per_min_kop")
    if kop is not None:
        try:
            return f"{int(kop) / 100:.2f} грн/хв"
        except Exception:
            pass
    return f"{p.get('rate_per_min_uah', 0)} грн/хв"


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

    text = (
        f"{p['desc']}\n\n"
        f"💸 *Тариф:* `{_rate_text(p)}`\n\n"
        f"Натисни «Купити», і я попрошу токен (BotFather), щоб створити твою копію."
    )

    await call.message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=marketplace_buy_kb(product_key),
    )
    await call.answer()


@router.callback_query(F.data.startswith("pl:mkp:buy:"))
async def cb_mkp_buy(call: CallbackQuery, state: FSMContext) -> None:
    if not call.message:
        await call.answer()
        return

    product_key = call.data.split("pl:mkp:buy:", 1)[1]

    # ✅ ВАЖЛИВО: тут саме buy_product, а не get_marketplace_product
    p = await buy_product(call.from_user.id, product_key)
    if not p:
        await call.answer("Не знайдено", show_alert=True)
        return

    await state.set_state(MarketplaceBuyFlow.waiting_bot_token)
    await state.update_data(mkp_product_key=product_key)

    await call.message.answer(
        "✅ *Покупка: створення твоєї копії*\n\n"
        "Встав *BotFather токен* бота, який буде працювати як твоя копія цього продукту.\n"
        "Формат: `123456:AA...`\n\n"
        "⚠️ Не кидай токен у публічні чати.",
        parse_mode="Markdown",
        reply_markup=back_to_menu_kb(),
    )
    await call.answer("Ок")


@router.callback_query(F.data == "pl:cabinet")
async def cb_cabinet(call: CallbackQuery) -> None:
    if call.message:
        try:
            await _render_cabinet(call.message)
        except Exception as e:
            log.exception("cb_cabinet failed: %s", e)
            await call.message.answer("⚠️ Кабінет тимчасово впав.", reply_markup=back_to_menu_kb())
    await call.answer()


@router.callback_query(F.data == "pl:my_bots")
async def cb_my_bots(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if call.message:
        await _render_my_bots(call.message)
    await call.answer()


@router.callback_query(F.data == "pl:my_bots:refresh")
async def cb_my_bots_refresh(call: CallbackQuery, state: FSMContext) -> None:
    await cb_my_bots(call, state)

@router.callback_query(F.data == "pl:my_bots:settings_stub")
async def cb_my_bots_settings_stub(call: CallbackQuery) -> None:
    if call.message:
        await call.message.answer(
            "⚙️ Налаштування (скоро)\n\n"
            "План:\n"
            "• встановлення тарифів по продуктам\n"
            "• VIP-режим (індивідуальна копія)\n"
            "• статистика списань\n",
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

@router.callback_query(F.data == "pl:about")
async def cb_about(call: CallbackQuery) -> None:
    if call.message:
        await call.message.answer(
            "ℹ️ *Про платформу*\n\n"
            "Rent Platform — маркетплейс ботів/модулів.\n"
            "Ти орендуєш продукт → підключаєш свого бота токеном → платиш з балансу/тарифу.\n\n"
            "Поточний статус: MVP (скелет) ✅",
            parse_mode="Markdown",
            reply_markup=back_to_menu_kb(),
        )
    await call.answer()


@router.callback_query(F.data == "pl:privacy")
async def cb_privacy(call: CallbackQuery) -> None:
    if call.message:
        await call.message.answer(
            "🔒 *Політика конфіденційності*\n\n"
            "• Токени ботів зберігаються для роботи оренди.\n"
            "• Не публікуй токени у чатах.\n"
            "• Дані використовуються лише для надання сервісу.\n\n"
            "_Пізніше винесемо в окрему сторінку/URL._",
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
            "• Платформа надає технічну оренду модулів/ботів.\n"
            "• При 0 балансі оренда може зупинитись автоматично.\n\n"
            "_Пізніше зробимо нормальний ToS документ._",
            parse_mode="Markdown",
            reply_markup=back_to_menu_kb(),
        )
    await call.answer()


@router.callback_query(F.data == "pl:commitments")
async def cb_commitments(call: CallbackQuery) -> None:
    if call.message:
        await call.message.answer(
            "🛡 *Наші зобовʼязання*\n\n"
            "• Мінімум доступів, тільки потрібне для роботи.\n"
            "• Прозорі списання в ledger.\n"
            "• Стабільність і контроль пауз/відновлення.\n\n"
            "_Далі — адмінка, статистика, платіжні інтеграції._",
            parse_mode="Markdown",
            reply_markup=back_to_menu_kb(),
        )
    await call.answer()


@router.callback_query(F.data.startswith("pl:partners:"))
async def cb_partners_sub(call: CallbackQuery) -> None:
    if not call.message:
        await call.answer()
        return

    key = call.data.split("pl:partners:", 1)[1]
    mapping = {
        "link": "🔗 *Моя реф-силка*\n\n(заглушка)",
        "stats": "📊 *Статистика*\n\n(заглушка)",
        "payouts": "💸 *Виплати*\n\n(заглушка)",
        "rules": "📜 *Правила*\n\n(заглушка)",
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


def _md_escape(text: str) -> str:
    # safe for Markdown (не V2)
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

    now = int(data.get("now") or time.time())
    bots = data.get("bots") or []

    # ✅ баланс
    balance_kop = int(data.get("balance_kop") or 0)
    balance_uah = balance_kop / 100.0

    if not bots:
        await message.answer(
            "👤 Кабінет\n\n"
            f"💰 Баланс: *{balance_uah:.2f} грн*\n\n"
            "Поки що немає підключених ботів.\n"
            "Йди в «Мої боти» і додай токен.",
            parse_mode="Markdown",
            reply_markup=back_to_menu_kb(),
        )
        await message.answer("Поповнення балансу:", reply_markup=cabinet_topup_kb())
        return

    lines = [
        "👤 Кабінет",
        "",
        f"🕒 Зараз: {_fmt_ts(now)}",
        f"💰 Баланс: *{balance_uah:.2f} грн*",
        "",
        "Твої боти і статуси:",
    ]

    for i, b in enumerate(bots, 1):
        st = (b.get("status") or "active").lower()
        plan = (b.get("plan_key") or "free")
        paid_until = int(b.get("paid_until_ts") or 0)
        expired = bool(b.get("expired"))
        paused_reason = b.get("paused_reason")

        badge = "✅ active" if st == "active" else ("⏸ paused" if st == "paused" else ("🗑 deleted" if st == "deleted" else st))
        pay_str = _fmt_ts(paid_until)
        pay_note = " ⚠️ прострочено" if expired else ""
        extra = f" (reason: {paused_reason})" if paused_reason else ""

        lines.append(
            f"{i}) {b.get('name','Bot')} — {badge}{extra}\n"
            f"   • plan: {plan}\n"
            f"   • paid_until: {pay_str}{pay_note}\n"
            f"   • id: {b['id']}"
        )

    await message.answer("\n".join(lines), parse_mode="Markdown", reply_markup=back_to_menu_kb())

    # ✅ кнопка поповнення
    await message.answer("Поповнення балансу:", reply_markup=cabinet_topup_kb())

    # Якщо прострочено — показуємо кнопку оплатити (MVP)
    for b in bots:
        if b.get("expired"):
            await message.answer(
                f"⚠️ Бот `{_md_escape(b['id'])}` прострочений. Щоб продовжити — натисни оплату 👇",
                parse_mode="Markdown",
                reply_markup=cabinet_pay_kb(b["id"]),
            )


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
        f"Бот: `{_md_escape(bot_id)}`\n"
        f"Період: *{months} міс*\n"
        f"Сума: *{invoice['amount_uah']} грн*\n\n"
        f"Посилання на оплату:\n{invoice['pay_url']}\n\n"
        f"_Після оплати зробимо авто-активацію (пізніше)._",
        parse_mode="Markdown",
        reply_markup=back_to_menu_kb(),
    )
    await call.answer("Створив інвойс ✅")


# ======================================================================
# Marketplace (продукти)
# ======================================================================

async def _render_marketplace_pick_bot(message: Message) -> None:
    items = await list_marketplace_products()

    if not items:
        await message.answer(
            "🧩 *Маркетплейс*\n\nПоки що немає продуктів 🙂",
            parse_mode="Markdown",
            reply_markup=back_to_menu_kb(),
        )
        return

    lines = ["🧩 *Маркетплейс ботів*", "", "Обери продукт 👇"]
    for it in items:
        lines.append(f"• *{it['title']}* — {it.get('short','')}")
        # показ тарифу (kop або uah)
        rate_text = _rate_text(it)
        if rate_text and rate_text != "0 грн/хв" and rate_text != "0.00 грн/хв":
            lines.append(f"   ⏱ Тариф: *{rate_text}*")

    await message.answer(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=marketplace_products_kb(items),
    )


# ======================================================================
# My Bots
# ======================================================================

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
            "🤖 *Мої боти*\n\nПоки порожньо.\nНатисни **➕ Додати бота** і встав токен.",
            parse_mode="Markdown",
            reply_markup=my_bots_kb(),
        )
        return

    lines = ["🤖 *Мої боти*"]
    for i, it in enumerate(items, 1):
        lines.append(f"{i}) **{it.get('name','Bot')}** — {_status_badge(it.get('status'))}  (id: `{it['id']}`)")

    await message.answer("\n".join(lines), parse_mode="Markdown", reply_markup=my_bots_kb())
    await message.answer("⚙️ Керування ботами:", reply_markup=my_bots_list_kb(items))


@router.callback_query(F.data == "pl:my_bots:add")
async def cb_my_bots_add(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(MyBotsFlow.waiting_token)
    if call.message:
        await call.message.answer(
            "➕ *Додати бота*\n\nВстав токен бота (BotFather: `123456:AA...`).",
            parse_mode="Markdown",
        )
    await call.answer()


@router.message(MarketplaceBuyFlow.waiting_bot_token, F.text)
async def mkp_receive_token(message: Message, state: FSMContext) -> None:
    token = (message.text or "").strip()
    data = await state.get_data()
    product_key = data.get("mkp_product_key")

    if not product_key:
        await state.clear()
        await message.answer(
            "⚠️ Стан покупки загубився. Зайди в Маркетплейс і натисни «Купити» ще раз.",
            reply_markup=back_to_menu_kb(),
        )
        return

    # ✅ валідація токена
    if ":" not in token or len(token) < 20:
        await message.answer("❌ Схоже на невалідний токен. Спробуй ще раз.")
        return

    # створюємо tenant (реальний токен)
    p = await get_marketplace_product(product_key)
    nice_name = (p["title"] if p else f"Product: {product_key}")

    tenant = await add_bot(
        message.from_user.id,
        token=token,
        name=nice_name,
        product_key=product_key,
    )
    await state.clear()

    await message.answer(
        f"✅ Готово! Твоя копія створена.\n\n"
        f"ID: `{tenant['id']}`\n"
        f"Продукт: `{product_key}`\n\n"
        f"Тепер зайди в «Мої боти» → знайди бота → ⚙️ Конфіг (ключі оплат).",
        parse_mode="Markdown",
        reply_markup=back_to_menu_kb(),
    )

@router.message(MyBotsFlow.waiting_token, F.text)
async def my_bots_receive_token(message: Message, state: FSMContext) -> None:
    token = (message.text or "").strip()

    if ":" not in token or len(token) < 20:
        await message.answer("❌ Схоже на невалідний токен. Спробуй ще раз.")
        return

    user_id = message.from_user.id
    await add_bot(user_id, token=token, name="Bot")

    await state.clear()
    await message.answer("✅ Додав.")
    await _render_my_bots(message)


@router.callback_query(F.data.startswith("pl:my_bots:noop:"))
async def cb_my_bots_noop(call: CallbackQuery) -> None:
    await call.answer("🙂")


@router.callback_query(F.data.startswith("pl:my_bots:pause:"))
async def cb_my_bots_pause(call: CallbackQuery) -> None:
    bot_id = call.data.split("pl:my_bots:pause:", 1)[1]
    ok = await pause_bot(call.from_user.id, bot_id)
    if call.message:
        await call.message.answer("⏸ Поставив на паузу." if ok else "⚠️ Не вийшло.")
        await _render_my_bots(call.message)
    await call.answer()


@router.callback_query(F.data.startswith("pl:my_bots:resume:"))
async def cb_my_bots_resume(call: CallbackQuery) -> None:
    bot_id = call.data.split("pl:my_bots:resume:", 1)[1]
    ok = await resume_bot(call.from_user.id, bot_id)
    if call.message:
        await call.message.answer("▶️ Відновив." if ok else "⚠️ Не вийшло.")
        await _render_my_bots(call.message)
    await call.answer()


@router.callback_query(F.data.startswith("pl:my_bots:del:"))
async def cb_my_bots_delete(call: CallbackQuery) -> None:
    bot_id = call.data.split("pl:my_bots:del:", 1)[1]
    ok = await delete_bot(call.from_user.id, bot_id)
    if call.message:
        await call.message.answer("🗑 Видалив (soft)." if ok else "⚠️ Не знайшов такого бота.")
        await _render_my_bots(call.message)
    await call.answer()


# ======================================================================
# Config (tenant keys)
# ======================================================================

async def _render_config(message: Message, bot_id: str) -> None:
    data = await get_bot_config(message.from_user.id, bot_id)
    if not data:
        await message.answer("⚠️ Не знайшов бота або нема доступу.", reply_markup=back_to_menu_kb())
        return

    providers = data["providers"]

    lines = [f"⚙️ *Конфіг бота* `{bot_id}`", ""]
    for p in providers:
        lines.append(f"{'✅' if p['enabled'] else '➕'} *{p['title']}*")
        for s in p.get("secrets") or []:
            lines.append(f"   • `{s['key']}` = {s['value_masked']}")

    await message.answer(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=config_kb(bot_id, providers),
    )


@router.callback_query(F.data.startswith("pl:cfg:open:"))
async def cb_cfg_open(call: CallbackQuery) -> None:
    if call.message:
        bot_id = call.data.split("pl:cfg:open:", 1)[1]
        await _render_config(call.message, bot_id)
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
        await _render_config(call.message, bot_id)


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
        f"⚠️ Не кидай це в публічні чати.",
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
        await message.answer("⚠️ Не вийшло зберегти (нема доступу або ключ не дозволений).", reply_markup=back_to_menu_kb())
        return

    await message.answer("✅ Зберіг.", reply_markup=back_to_menu_kb())
    await _render_config(message, bot_id)
# ДОДАЙ В САМ КІНЕЦЬ rent_platform/platform/handlers/start.py

# ======================================================================
# TopUp (баланс)
# ======================================================================

@router.callback_query(F.data == "pl:topup:start")
async def cb_topup_start(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TopUpFlow.waiting_amount)
    if call.message:
        await call.message.answer(
            "💰 *Поповнення балансу*\n\n"
            "Введи суму в гривнях (цілим числом), наприклад: `200`",
            parse_mode="Markdown",
            reply_markup=back_to_menu_kb(),
        )
    await call.answer()


@router.message(TopUpFlow.waiting_amount, F.text)
async def topup_receive_amount(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip().replace(" ", "")
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

    if res.get("already"):
        await call.message.answer("ℹ️ Цей інвойс вже не pending.")
        await call.answer()
        return

    new_balance = (int(res["new_balance_kop"]) / 100.0)
    added = (int(res["amount_kop"]) / 100.0)
    await call.message.answer(
        f"✅ Оплату підтверджено (тест). Баланс +{added:.2f} грн.\n"
        f"💰 Новий баланс: {new_balance:.2f} грн",
        reply_markup=back_to_menu_kb(),
    )
    await call.answer("✅")


@router.message(F.text)
async def _debug_unhandled_text(message: Message, state: FSMContext) -> None:
    st = await state.get_state()
    if st:
        # якщо ми в якомусь flow — не заважаємо
        return

    log.warning(
        "UNHANDLED TEXT: %r | chat=%s user=%s",
        message.text,
        getattr(getattr(message, "chat", None), "id", None),
        getattr(getattr(message, "from_user", None), "id", None),
    )
    await message.answer("Не зрозумів команду 🙂 Натисни «Меню» або /start")