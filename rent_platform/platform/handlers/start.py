from __future__ import annotations

import logging
import datetime as _dt

from aiogram import Router, F
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from rent_platform.platform.handlers.cabinet import register_cabinet, render_cabinet

from rent_platform.platform.keyboards import (
    # my bots
    my_bots_kb,
    my_bots_list_kb,

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


def _label(message: Message) -> str:
    chat_id = message.chat.id if message.chat else None
    user_id = message.from_user.id if message.from_user else None
    return f"chat={chat_id}, user={user_id}"


def _md_escape(text: str) -> str:
    # Markdown (не V2)
    return (
        str(text)
        .replace("_", "\\_")
        .replace("*", "\\*")
        .replace("`", "\\`")
        .replace("[", "\\[")
    )


async def _send_main_menu(message: Message) -> None:
    text = (
        "✅ *Rent Platform запущено*\n\n"
        "Обери розділ 👇\n\n"
        "🧩 *Маркетплейс* — продукти/оренда\n"
        "🤖 *Мої боти* — керування копіями\n"
        "👤 *Кабінет* — баланс / тарифи / історія\n"
        "🤝 *Партнери* — рефералка / виплати\n"
        "🆘 *Підтримка* — інформація / правила\n"
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
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    log.info("platform /start: %s", _label(message))
    await _send_main_menu(message)


# ======================================================================
# Partners / Support helpers (called from menu handler)
# ======================================================================
async def partners_text(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "🤝 *Партнерська програма*\n\n"
        "Рефералка + статистика + виплати.\n"
        "_MVP: заглушки, але структура вже є._",
        parse_mode="Markdown",
        reply_markup=partners_inline_kb(),
    )


async def support_text(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "🆘 *Підтримка*\n\n"
        "Тут буде база знань, правила, контакти.\n"
        "Поки що — загальна інформація 👇",
        parse_mode="Markdown",
        reply_markup=about_inline_kb(),
    )


# ======================================================================
# Inline callbacks
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


@router.callback_query(F.data == "pl:my_bots:refresh")
async def cb_my_bots_refresh(call: CallbackQuery, state: FSMContext) -> None:
    await cb_my_bots(call, state)


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
            "🆘 *Підтримка*\n\nТакож є «Загальна інформація» нижче 👇",
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
            "Потік: *обрав продукт* → *підключив токен* → *списання з балансу*.\n\n"
            "Статус: *MVP працює* ✅",
            parse_mode="Markdown",
            reply_markup=back_to_menu_kb(),
        )
    await call.answer()


@router.callback_query(F.data == "pl:privacy")
async def cb_privacy(call: CallbackQuery) -> None:
    if call.message:
        await call.message.answer(
            "🔒 *Політика конфіденційності*\n\n"
            "• Токени ботів зберігаються тільки для роботи оренди.\n"
            "• Не публікуй токени у чатах.\n"
            "• Дані використовуються лише для надання сервісу.\n\n"
            "_Пізніше винесемо в окремий URL._",
            parse_mode="Markdown",
            reply_markup=back_to_menu_kb(),
        )
    await call.answer()


@router.callback_query(F.data == "pl:terms")
async def cb_terms(call: CallbackQuery) -> None:
    if call.message:
        await call.message.answer(
            "📄 *Умови користування*\n\n"
            "• Ти відповідаєш за контент/дії свого бота.\n"
            "• Платформа надає технічну оренду модулів.\n"
            "• При 0 балансі — оренда може стати на паузу.\n\n"
            "_Пізніше — нормальний документ._",
            parse_mode="Markdown",
            reply_markup=back_to_menu_kb(),
        )
    await call.answer()


@router.callback_query(F.data == "pl:commitments")
async def cb_commitments(call: CallbackQuery) -> None:
    if call.message:
        await call.message.answer(
            "🛡 *Наші зобовʼязання*\n\n"
            "• Мінімум доступів.\n"
            "• Прозорі списання (ledger).\n"
            "• Контроль пауз/відновлення.\n\n"
            "_Далі: адмінка, статистика, реальні оплати._",
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
        "link": "🔗 *Моя реф-силка*\n\n_MVP: заглушка_",
        "stats": "📊 *Статистика*\n\n_MVP: заглушка_",
        "payouts": "💸 *Виплати*\n\n_MVP: заглушка_",
        "rules": "📜 *Правила*\n\n_MVP: заглушка_",
    }
    await call.message.answer(
        mapping.get(key, "Пункт у розробці."),
        parse_mode="Markdown",
        reply_markup=partners_inline_kb(),
    )
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


@router.message(MarketplaceBuyFlow.waiting_bot_token, F.text)
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
        "Далі: «Мої боти» → ⚙️ «Конфіг» (ключі оплат/інтеграцій).",
        parse_mode="Markdown",
        reply_markup=back_to_menu_kb(),
    )


# ======================================================================
# My Bots — згруповано та акуратно
# ======================================================================
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


def _fmt_paid_until(ts: int | None) -> str:
    try:
        ts_i = int(ts or 0)
    except Exception:
        ts_i = 0
    if ts_i <= 0:
        return "—"
    return _dt.datetime.fromtimestamp(ts_i).strftime("%Y-%m-%d %H:%M")


def _group_key(it: dict) -> str:
    st = (it.get("status") or "active").lower()
    if st == "active":
        return "active"
    if st == "paused":
        return "paused"
    if st == "deleted":
        return "deleted"
    return "other"


def _section_title(key: str, count: int) -> str:
    if key == "active":
        return f"🟢 *Активні* — *{count}*"
    if key == "paused":
        return f"⏸ *На паузі* — *{count}*"
    if key == "deleted":
        return f"🗑 *Видалені* — *{count}*"
    return f"⚪️ *Інші* — *{count}*"


async def _render_my_bots(message: Message) -> None:
    user_id = message.from_user.id
    items = await list_bots(user_id)

    if not items:
        await message.answer(
            "🤖 *Мої боти*\n\n"
            "Поки порожньо.\n"
            "Натисни *➕ Додати бота* і встав токен.",
            parse_mode="Markdown",
            reply_markup=my_bots_kb(),
        )
        return

    grouped: dict[str, list[dict]] = {"active": [], "paused": [], "deleted": [], "other": []}
    for it in items:
        grouped[_group_key(it)].append(it)

    total = len(items)
    active_n = len(grouped["active"])
    paused_n = len(grouped["paused"])
    deleted_n = len(grouped["deleted"])

    header = (
        "🤖 *Мої боти*\n\n"
        f"Всього: *{total}*  •  🟢 *{active_n}*  ⏸ *{paused_n}*  🗑 *{deleted_n}*\n"
    )

    lines: list[str] = [header]
    section_order = ["active", "paused", "deleted", "other"]
    idx = 0

    for sec in section_order:
        sec_items = grouped[sec]
        if not sec_items:
            continue

        lines.append(_section_title(sec, len(sec_items)))
        lines.append("")

        for it in sec_items:
            idx += 1
            name = it.get("name") or "Бот"
            bot_id = it["id"]

            st_badge = _status_badge(it.get("status"), it.get("paused_reason"))

            pk = (it.get("product_key") or "").strip()
            pk_s = pk if pk else "—"

            paid_until = _fmt_paid_until(it.get("paid_until_ts"))
            plan = (it.get("plan_key") or "free").strip()

            lines.append(f"{idx}) *{_md_escape(name)}*")
            lines.append(f"   {st_badge}  •  id: `{bot_id}`")
            lines.append(f"   🧩 продукт: `{pk_s}`  •  📦 план: `{plan}`")
            lines.append(f"   ⏳ оплачено до: `{paid_until}`")
            lines.append("")

        lines.append("")

    await message.answer(
        "\n".join(lines).strip(),
        parse_mode="Markdown",
        reply_markup=my_bots_kb(),
    )

    await message.answer(
        "⚙️ *Керування ботами*",
        parse_mode="Markdown",
        reply_markup=my_bots_list_kb(items),
    )


@router.callback_query(F.data == "pl:my_bots:add")
async def cb_my_bots_add(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(MyBotsFlow.waiting_token)
    if call.message:
        await call.message.answer(
            "➕ *Додати бота*\n\nВстав токен (BotFather: `123456:AA...`).",
            parse_mode="Markdown",
            reply_markup=back_to_menu_kb(),
        )
    await call.answer()


@router.message(MyBotsFlow.waiting_token, F.text)
async def my_bots_receive_token(message: Message, state: FSMContext) -> None:
    token = (message.text or "").strip()

    if ":" not in token or len(token) < 20:
        await message.answer("❌ Схоже на невалідний токен. Спробуй ще раз.")
        return

    user_id = message.from_user.id
    await add_bot(user_id, token=token, name="Бот")

    await state.clear()
    await message.answer("✅ Додав.", reply_markup=back_to_menu_kb())
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
    await _render_config(message, bot_id)


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

    if res.get("already"):
        await call.message.answer("ℹ️ Цей інвойс вже не pending.")
        await call.answer()
        return

    new_balance = int(res["new_balance_kop"]) / 100.0
    added = int(res["amount_kop"]) / 100.0
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
        return

    log.warning(
        "UNHANDLED TEXT: %r | chat=%s user=%s",
        message.text,
        getattr(getattr(message, "chat", None), "id", None),
        getattr(getattr(message, "from_user", None), "id", None),
    )
    await message.answer("Не зрозумів 🙂 Натисни «Меню» або /start")