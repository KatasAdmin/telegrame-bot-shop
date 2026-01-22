from __future__ import annotations

import json
from typing import Any

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from rent_platform.config import settings
from rent_platform.db.repo import PlatformSettingsRepo
from rent_platform.products.catalog import PRODUCT_CATALOG

router = Router()


def is_admin(user_id: int) -> bool:
    s = (getattr(settings, "ADMIN_USER_IDS", "") or "").strip()
    if not s:
        return False
    allowed = {int(x.strip()) for x in s.split(",") if x.strip().isdigit()}
    return int(user_id) in allowed


# ---------- platform settings helpers ----------

async def _ps_get() -> dict[str, Any]:
    s = await PlatformSettingsRepo.get()
    if not s:
        s = {}
    # якщо з БД прийшов json-рядок
    if isinstance(s, str):
        try:
            s = json.loads(s)
        except Exception:
            s = {}
    return dict(s)


async def _ps_set(new_settings: dict[str, Any]) -> None:
    """
    В ідеалі PlatformSettingsRepo має мати set()/upsert().
    Якщо в тебе метод називається інакше — скажи, я піджене під твій repo.
    """
    fn = getattr(PlatformSettingsRepo, "set", None) or getattr(PlatformSettingsRepo, "upsert", None)
    if not callable(fn):
        raise RuntimeError("PlatformSettingsRepo.set/upsert not found")
    await fn(new_settings)


def _get_overrides(s: dict[str, Any]) -> dict[str, Any]:
    ov = s.get("marketplace_overrides") or {}
    if isinstance(ov, str):
        try:
            ov = json.loads(ov)
        except Exception:
            ov = {}
    if not isinstance(ov, dict):
        ov = {}
    return ov


# ---------- UI ----------

def admin_menu_kb() -> Any:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🤝 Партнерка (% / мін. виплата)", callback_data="adm:open:ref"))
    kb.row(InlineKeyboardButton(text="💸 Pending виплати", callback_data="adm:open:payouts"))
    kb.row(
        InlineKeyboardButton(text="🧩 Продукти маркетплейсу", callback_data="adm:products"),
        InlineKeyboardButton(text="🖼 Банер кабінету", callback_data="adm:banner"),
    )
    kb.row(InlineKeyboardButton(text="↩️ В меню", callback_data="adm:close"))
    return kb.as_markup()


@router.message(F.text == "/admin")
async def admin_cmd(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "⚙️ *Адмін-панель (MVP)*\n\nОбери дію 👇",
        parse_mode="Markdown",
        reply_markup=admin_menu_kb(),
    )


@router.callback_query(F.data == "adm:close")
async def adm_close(call: CallbackQuery) -> None:
    await call.answer()
    # нічого не робимо, просто “закрили” адмінку


# ======================================================================
# Banner cabinet
# ======================================================================

class AdminBannerFlow(StatesGroup):
    waiting_url = State()


@router.callback_query(F.data == "adm:banner")
async def adm_banner(call: CallbackQuery, state: FSMContext) -> None:
    if not call.message or not is_admin(call.from_user.id):
        await call.answer()
        return

    s = await _ps_get()
    cur = (s.get("cabinet_banner_url") or "").strip()

    txt = "🖼 *Банер кабінету*\n\n"
    txt += f"Поточний URL:\n`{cur or '—'}`\n\n"
    txt += "Відправ сюди *новий URL* (або `-` щоб прибрати)."

    await state.set_state(AdminBannerFlow.waiting_url)
    await call.message.answer(txt, parse_mode="Markdown")
    await call.answer()


@router.message(AdminBannerFlow.waiting_url, F.text)
async def adm_banner_receive(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    url = (message.text or "").strip()
    await state.clear()

    s = await _ps_get()
    if url == "-" or url.lower() in {"none", "null"}:
        s["cabinet_banner_url"] = ""
    else:
        # мінімальна валідація
        if not (url.startswith("http://") or url.startswith("https://")):
            await message.answer("❌ URL має починатися з http:// або https://")
            return
        s["cabinet_banner_url"] = url

    await _ps_set(s)
    await message.answer("✅ Збережено. Перевір у «Кабінет».")


# ======================================================================
# Marketplace products
# ======================================================================

class AdminProductFlow(StatesGroup):
    waiting_rate = State()


def _product_title(key: str, meta: dict, ov: dict) -> str:
    title = meta.get("title") or key
    enabled = ov.get(key, {}).get("enabled", True)
    mark = "✅" if enabled else "⛔️"
    return f"{mark} {title}"


def products_kb(ov: dict) -> Any:
    kb = InlineKeyboardBuilder()
    for key, meta in PRODUCT_CATALOG.items():
        kb.row(
            InlineKeyboardButton(
                text=_product_title(key, meta, ov),
                callback_data=f"adm:prod:{key}",
            )
        )
    kb.row(InlineKeyboardButton(text="↩️ Назад", callback_data="adm:back"))
    return kb.as_markup()


@router.callback_query(F.data == "adm:products")
async def adm_products(call: CallbackQuery) -> None:
    if not call.message or not is_admin(call.from_user.id):
        await call.answer()
        return

    s = await _ps_get()
    ov = _get_overrides(s)

    await call.message.answer(
        "🧩 *Продукти маркетплейсу*\n\n"
        "✅ = показується/доступний\n"
        "⛔️ = прихований/вимкнений\n\n"
        "Вибери продукт 👇",
        parse_mode="Markdown",
        reply_markup=products_kb(ov),
    )
    await call.answer()


@router.callback_query(F.data == "adm:back")
async def adm_back(call: CallbackQuery) -> None:
    if not call.message or not is_admin(call.from_user.id):
        await call.answer()
        return
    await call.message.answer("⚙️ *Адмін-панель (MVP)*\n\nОбери дію 👇", parse_mode="Markdown", reply_markup=admin_menu_kb())
    await call.answer()


def product_actions_kb(key: str, enabled: bool) -> Any:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(
            text=("⛔️ Вимкнути" if enabled else "✅ Увімкнути"),
            callback_data=f"adm:prod:{key}:toggle",
        )
    )
    kb.row(
        InlineKeyboardButton(text="✏️ Змінити тариф (грн/хв)", callback_data=f"adm:prod:{key}:rate"),
        InlineKeyboardButton(text="♻️ Скинути override", callback_data=f"adm:prod:{key}:reset"),
    )
    kb.row(InlineKeyboardButton(text="↩️ До списку", callback_data="adm:products"))
    return kb.as_markup()


@router.callback_query(F.data.startswith("adm:prod:"))
async def adm_product_open(call: CallbackQuery, state: FSMContext) -> None:
    if not call.message or not is_admin(call.from_user.id):
        await call.answer()
        return

    parts = call.data.split(":")
    # adm:prod:<key>  або adm:prod:<key>:action
    key = parts[2]
    action = parts[3] if len(parts) > 3 else ""

    if key not in PRODUCT_CATALOG:
        await call.message.answer("⚠️ Невідомий продукт.")
        await call.answer()
        return

    s = await _ps_get()
    ov = _get_overrides(s)
    ov.setdefault(key, {})
    enabled = bool(ov[key].get("enabled", True))

    if action == "toggle":
        ov[key]["enabled"] = not enabled
        s["marketplace_overrides"] = ov
        await _ps_set(s)
        enabled = bool(ov[key].get("enabled", True))
        await call.message.answer("✅ Оновлено.")
        await call.message.answer(f"🧩 *{PRODUCT_CATALOG[key].get('title', key)}*", parse_mode="Markdown",
                                reply_markup=product_actions_kb(key, enabled))
        await call.answer()
        return

    if action == "reset":
        # прибираємо override тарифу, але enabled лишаємо якщо треба
        keep_enabled = ov[key].get("enabled", True)
        ov[key] = {"enabled": keep_enabled}
        s["marketplace_overrides"] = ov
        await _ps_set(s)
        await call.message.answer("♻️ Override скинуто (тариф з PRODUCT_CATALOG).")
        await call.message.answer(f"🧩 *{PRODUCT_CATALOG[key].get('title', key)}*", parse_mode="Markdown",
                                reply_markup=product_actions_kb(key, bool(keep_enabled)))
        await call.answer()
        return

    if action == "rate":
        await state.set_state(AdminProductFlow.waiting_rate)
        await state.update_data(prod_key=key)
        cur_rate = ov[key].get("rate_per_min_uah", PRODUCT_CATALOG[key].get("rate_per_min_uah", 0))
        await call.message.answer(
            f"✏️ Введи *новий тариф* для `{key}` в грн/хв.\n"
            f"Поточний: *{float(cur_rate):.2f}*\n\n"
            f"Напр: `1` або `0.5`",
            parse_mode="Markdown",
        )
        await call.answer()
        return

    # default: show product card
    meta = PRODUCT_CATALOG[key]
    base_rate = float(meta.get("rate_per_min_uah", 0) or 0)
    cur_rate = float(ov.get(key, {}).get("rate_per_min_uah", base_rate) or 0)

    txt = (
        f"🧩 *{meta.get('title', key)}*\n"
        f"key: `{key}`\n\n"
        f"Статус: *{'ON ✅' if enabled else 'OFF ⛔️'}*\n"
        f"Тариф: *{cur_rate:.2f} грн/хв*"
    )
    await call.message.answer(txt, parse_mode="Markdown", reply_markup=product_actions_kb(key, enabled))
    await call.answer()


@router.message(AdminProductFlow.waiting_rate, F.text)
async def adm_product_set_rate(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    data = await state.get_data()
    key = data.get("prod_key")
    await state.clear()

    if not key or key not in PRODUCT_CATALOG:
        await message.answer("⚠️ Невідомий продукт.")
        return

    raw = (message.text or "").strip().replace(",", ".")
    try:
        val = float(raw)
        if val < 0:
            raise ValueError
    except Exception:
        await message.answer("❌ Невалідне число. Приклад: 1 або 0.5")
        return

    s = await _ps_get()
    ov = _get_overrides(s)
    ov.setdefault(key, {})
    ov[key]["rate_per_min_uah"] = float(val)
    if "enabled" not in ov[key]:
        ov[key]["enabled"] = True

    s["marketplace_overrides"] = ov
    await _ps_set(s)

    enabled = bool(ov[key].get("enabled", True))
    await message.answer("✅ Тариф оновлено.")
    await message.answer(
        f"🧩 *{PRODUCT_CATALOG[key].get('title', key)}*\nТариф: *{val:.2f} грн/хв*",
        parse_mode="Markdown",
        reply_markup=product_actions_kb(key, enabled),
    )