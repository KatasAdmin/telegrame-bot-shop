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


# ---------- platform settings helpers (ref_json as single config store) ----------

async def _ps_get() -> dict[str, Any]:
    # ref_json містить і рефералку, і marketplace_overrides
    s = await PlatformSettingsRepo.get_ref_settings()
    if not isinstance(s, dict):
        return {}
    return dict(s)


async def _ps_set(s: dict[str, Any]) -> None:
    if not isinstance(s, dict):
        s = {}
    await PlatformSettingsRepo.set_ref_settings(s)


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
    kb.row(InlineKeyboardButton(text="↩️ В меню", callback_data="adm:back_to_menu"))
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


@router.callback_query(F.data == "adm:back_to_menu")
async def adm_back_to_menu(call: CallbackQuery) -> None:
    if not call.message or not is_admin(call.from_user.id):
        await call.answer()
        return
    await call.message.answer(
        "⚙️ *Адмін-панель (MVP)*\n\nОбери дію 👇",
        parse_mode="Markdown",
        reply_markup=admin_menu_kb(),
    )
    await call.answer()


# ======================================================================
# Partner buttons -> just hint user (real logic in admin_ref.py)
# ======================================================================

@router.callback_query(F.data == "adm:open:ref")
async def adm_open_ref(call: CallbackQuery) -> None:
    if not call.message or not is_admin(call.from_user.id):
        await call.answer()
        return
    await call.message.answer("👉 Рефералка: відкрий команду /admin_ref")
    await call.answer()


@router.callback_query(F.data == "adm:open:payouts")
async def adm_open_payouts(call: CallbackQuery) -> None:
    if not call.message or not is_admin(call.from_user.id):
        await call.answer()
        return
    await call.message.answer("👉 Pending виплати: відкрий /admin_ref і натисни «📥 Pending заявки»")
    await call.answer()


# ======================================================================
# Banner cabinet (PHOTO + URL fallback) -> stored in platform_settings.cabinet_banner_url
# ======================================================================

class AdminBannerFlow(StatesGroup):
    waiting_banner = State()


@router.callback_query(F.data == "adm:banner")
async def adm_banner(call: CallbackQuery, state: FSMContext) -> None:
    if not call.message or not is_admin(call.from_user.id):
        await call.answer()
        return

    row = await PlatformSettingsRepo.get() or {}
    cur = (row.get("cabinet_banner_url") or "").strip()

    txt = "🖼 *Банер кабінету*\n\n"
    txt += f"Поточне значення:\n`{cur or '—'}`\n\n"
    txt += (
        "Надішли *фото* (найкраще) — я збережу його як банер.\n"
        "Або надішли *URL* (http/https).\n"
        "Щоб прибрати — напиши `-`."
    )

    await state.set_state(AdminBannerFlow.waiting_banner)
    await call.message.answer(txt, parse_mode="Markdown")
    await call.answer()


@router.message(AdminBannerFlow.waiting_banner, F.text)
async def adm_banner_receive_text(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    raw = (message.text or "").strip()
    await state.clear()

    if raw == "-" or raw.lower() in {"none", "null"}:
        await PlatformSettingsRepo.upsert_cabinet_banner("")
        await message.answer("✅ Банер прибрано. Перевір у «Кабінет».", reply_markup=admin_menu_kb())
        return

    if not (raw.startswith("http://") or raw.startswith("https://")):
        await message.answer("❌ Надішли *фото* або URL який починається з http:// чи https:// (або `-`).", parse_mode="Markdown")
        return

    await PlatformSettingsRepo.upsert_cabinet_banner(raw)
    await message.answer("✅ Банер оновлено. Перевір у «Кабінет».", reply_markup=admin_menu_kb())


@router.message(AdminBannerFlow.waiting_banner, F.photo)
async def adm_banner_receive_photo(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    await state.clear()

    file_id = message.photo[-1].file_id  # найбільше фото
    await PlatformSettingsRepo.upsert_cabinet_banner(file_id)

    await message.answer("✅ Банер оновлено. Перевір у «Кабінет».", reply_markup=admin_menu_kb())
    await message.answer_photo(file_id, caption="Ось банер зараз ✅")


@router.message(AdminBannerFlow.waiting_banner)
async def adm_banner_wrong_type(message: Message) -> None:
    await message.answer("❌ Потрібно *фото* або *URL*. Або `-` щоб прибрати.", parse_mode="Markdown")


# ======================================================================
# Marketplace products (stored in ref_json.marketplace_overrides)
# ======================================================================

class AdminProductFlow(StatesGroup):
    waiting_rate = State()


def _product_title(key: str, meta: dict, ov: dict) -> str:
    title = meta.get("title") or key
    enabled = bool(ov.get(key, {}).get("enabled", True))
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
    await call.message.answer(
        "⚙️ *Адмін-панель (MVP)*\n\nОбери дію 👇",
        parse_mode="Markdown",
        reply_markup=admin_menu_kb(),
    )
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


def _rate_current_for(key: str, ov: dict) -> float:
    meta = PRODUCT_CATALOG.get(key, {}) or {}
    base_rate = float(meta.get("rate_per_min_uah", 0) or 0)
    cur = ov.get(key, {}).get("rate_per_min_uah", base_rate)
    try:
        return float(cur)
    except Exception:
        return base_rate


@router.callback_query(F.data.startswith("adm:prod:"))
async def adm_product_open(call: CallbackQuery, state: FSMContext) -> None:
    if not call.message or not is_admin(call.from_user.id):
        await call.answer()
        return

    parts = call.data.split(":")
    # adm:prod:<key>  або adm:prod:<key>:action
    key = parts[2] if len(parts) > 2 else ""
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

        enabled2 = bool(ov[key].get("enabled", True))
        await call.message.answer("✅ Оновлено.")
        await call.message.answer(
            f"🧩 *{PRODUCT_CATALOG[key].get('title', key)}*",
            parse_mode="Markdown",
            reply_markup=product_actions_kb(key, enabled2),
        )
        await call.answer()
        return

    if action == "reset":
        keep_enabled = bool(ov[key].get("enabled", True))
        ov[key] = {"enabled": keep_enabled}
        s["marketplace_overrides"] = ov
        await _ps_set(s)

        await call.message.answer("♻️ Override скинуто (тариф з PRODUCT_CATALOG).")
        await call.message.answer(
            f"🧩 *{PRODUCT_CATALOG[key].get('title', key)}*",
            parse_mode="Markdown",
            reply_markup=product_actions_kb(key, keep_enabled),
        )
        await call.answer()
        return

    if action == "rate":
        await state.set_state(AdminProductFlow.waiting_rate)
        await state.update_data(prod_key=key)
        cur_rate = _rate_current_for(key, ov)
        await call.message.answer(
            f"✏️ Введи *новий тариф* для `{key}` в грн/хв.\n"
            f"Поточний: *{cur_rate:.2f}*\n\n"
            f"Напр: `1` або `0.5`",
            parse_mode="Markdown",
        )
        await call.answer()
        return

    # default: show product card
    meta = PRODUCT_CATALOG[key]
    cur_rate = _rate_current_for(key, ov)

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