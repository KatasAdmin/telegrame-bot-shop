from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# === Тексти кнопок (одним місцем) ===
BTN_MARKETPLACE = "🧩 Маркетплейс"
BTN_MY_BOTS = "🤖 Мої боти"
BTN_CABINET = "👤 Кабінет"
BTN_PARTNERS = "🤝 Партнери"
BTN_HELP = "🆘 Підтримка"

BTN_ADMIN = "🛠 Адмінка (скоро)"


def main_menu_kb(is_admin: bool = False) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text=BTN_MARKETPLACE), KeyboardButton(text=BTN_MY_BOTS)],
        [KeyboardButton(text=BTN_CABINET), KeyboardButton(text=BTN_PARTNERS)],
        [KeyboardButton(text=BTN_HELP)],
    ]
    if is_admin:
        keyboard.append([KeyboardButton(text=BTN_ADMIN)])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Обери розділ 👇",
    )


def main_menu_inline_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text=BTN_MARKETPLACE, callback_data="pl:marketplace"),
        InlineKeyboardButton(text=BTN_MY_BOTS, callback_data="pl:my_bots"),
        width=2,
    )
    kb.row(
        InlineKeyboardButton(text=BTN_CABINET, callback_data="pl:cabinet"),
        InlineKeyboardButton(text=BTN_PARTNERS, callback_data="pl:partners"),
        width=2,
    )
    kb.row(InlineKeyboardButton(text=BTN_HELP, callback_data="pl:support"), width=1)
    return kb.as_markup()


def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ В меню", callback_data="pl:menu")]]
    )


def partners_inline_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="🔗 Моя реф-силка", callback_data="pl:partners:link"),
        InlineKeyboardButton(text="📊 Статистика", callback_data="pl:partners:stats"),
        width=2,
    )
    kb.row(
        InlineKeyboardButton(text="💸 Виплати", callback_data="pl:partners:payouts"),
        InlineKeyboardButton(text="📜 Правила", callback_data="pl:partners:rules"),
        width=2,
    )
    kb.row(InlineKeyboardButton(text="⬅️ В меню", callback_data="pl:menu"))
    return kb.as_markup()


def about_inline_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="ℹ️ Про платформу", callback_data="pl:about"),
        InlineKeyboardButton(text="🔒 Політика конфіденційності", callback_data="pl:privacy"),
        width=1,
    )
    kb.row(
        InlineKeyboardButton(text="📄 Умови користування", callback_data="pl:terms"),
        InlineKeyboardButton(text="🛡 Наші зобовʼязання", callback_data="pl:commitments"),
        width=1,
    )
    kb.row(InlineKeyboardButton(text="⬅️ В меню", callback_data="pl:menu"))
    return kb.as_markup()


# === My bots ===

def my_bots_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="➕ Додати бота", callback_data="pl:my_bots:add"),
        InlineKeyboardButton(text="🔄 Оновити", callback_data="pl:my_bots:refresh"),
        width=2,
    )
    kb.row(
        InlineKeyboardButton(text="⚙️ Налаштування (скоро)", callback_data="pl:my_bots:settings_stub"),
        width=1,
    )
    kb.row(InlineKeyboardButton(text="⬅️ В меню", callback_data="pl:menu"), width=1)
    return kb.as_markup()


def my_bots_list_kb(items: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()

    for it in items:
        bot_id = it["id"]
        name = it.get("name") or "Bot"
        st = (it.get("status") or "active").lower()

        badge = (
            "✅ active" if st == "active"
            else "⏸ paused" if st == "paused"
            else "🗑 deleted" if st == "deleted"
            else st
        )

        kb.row(
            InlineKeyboardButton(
                text=f"🤖 {name} — {badge}",
                callback_data=f"pl:my_bots:noop:{bot_id}",
            )
        )

        if st in ("active", "paused"):
            kb.row(
                InlineKeyboardButton(text="⚙️ Конфіг", callback_data=f"pl:cfg:open:{bot_id}"),
                InlineKeyboardButton(
                    text=("⏸ Пауза" if st == "active" else "▶️ Відновити"),
                    callback_data=(f"pl:my_bots:pause:{bot_id}" if st == "active" else f"pl:my_bots:resume:{bot_id}"),
                ),
                width=2,
            )
            kb.row(
                InlineKeyboardButton(text="🗑 Видалити", callback_data=f"pl:my_bots:del:{bot_id}"),
                width=1,
            )
        else:
            kb.row(
                InlineKeyboardButton(text="🙂 (недоступно)", callback_data=f"pl:my_bots:noop:{bot_id}")
            )

    kb.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="pl:my_bots"), width=1)
    return kb.as_markup()


# === Marketplace (модулі) ===

def marketplace_bots_kb(items: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for it in items:
        bot_id = it["id"]
        name = it.get("name") or "Bot"
        st = (it.get("status") or "active").lower()
        badge = "✅" if st == "active" else ("⏸" if st == "paused" else "🗑")
        kb.row(InlineKeyboardButton(text=f"{badge} {name} (id: {bot_id})", callback_data=f"pl:mp:bot:{bot_id}"))
    kb.row(InlineKeyboardButton(text="⬅️ В меню", callback_data="pl:menu"))
    return kb.as_markup()


def marketplace_modules_kb(bot_id: str, modules: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()

    for m in modules:
        key = m["key"]
        title = m.get("title") or key
        enabled = bool(m.get("enabled"))

        btn_text = f"{'✅' if enabled else '➕'} {title}"
        kb.row(
            InlineKeyboardButton(
                text=btn_text,
                callback_data=f"pl:mp:tg:{bot_id}:{key}",
            )
        )

    kb.row(
        InlineKeyboardButton(text="🔄 Оновити", callback_data=f"pl:mp:bot:{bot_id}"),
        InlineKeyboardButton(text="⬅️ До ботів", callback_data="pl:marketplace"),
        width=2,
    )
    kb.row(InlineKeyboardButton(text="⬅️ В меню", callback_data="pl:menu"))
    return kb.as_markup()


def marketplace_products_kb(items: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for it in items:
        kb.row(
            InlineKeyboardButton(
                text=f"{it['title']}",
                callback_data=f"pl:mkp:open:{it['key']}",
            )
        )
        kb.row(
            InlineKeyboardButton(
                text=f"⚡ {it.get('rate_per_min_uah', 0)} грн/хв",
                callback_data=f"pl:mkp:open:{it['key']}",
            )
        )
    kb.row(InlineKeyboardButton(text="⬅️ В меню", callback_data="pl:menu"))
    return kb.as_markup()


def marketplace_buy_kb(product_key: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🛍 Купити з балансу", callback_data=f"pl:mkp:buy:{product_key}"))
    kb.row(InlineKeyboardButton(text="💳 Купити банком (скоро)", callback_data="pl:noop"))
    kb.row(InlineKeyboardButton(text="🪙 Купити криптою (скоро)", callback_data="pl:noop"))
    kb.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="pl:marketplace"))
    kb.row(InlineKeyboardButton(text="⬅️ В меню", callback_data="pl:menu"))
    return kb.as_markup()
# === Cabinet pay ===

def cabinet_pay_kb(bot_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="💳 Оплатити (1 міс)", callback_data=f"pl:pay:{bot_id}:1"))
    kb.row(InlineKeyboardButton(text="⬅️ В меню", callback_data="pl:menu"))
    return kb.as_markup()


# === Config (tenant keys) ===

def config_kb(bot_id: str, providers: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()

    for p in providers:
        prov = p["provider"]
        title = p["title"]
        enabled = bool(p["enabled"])
        kb.row(
            InlineKeyboardButton(
                text=f"{'✅' if enabled else '➕'} {title}",
                callback_data=f"pl:cfg:tg:{bot_id}:{prov}",
            )
        )
        for s in p.get("secrets") or []:
            kb.row(
                InlineKeyboardButton(
                    text=f"🔑 {s['label']}",
                    callback_data=f"pl:cfg:set:{bot_id}:{s['key']}",
                )
            )

    kb.row(
        InlineKeyboardButton(text="🔄 Оновити", callback_data=f"pl:cfg:open:{bot_id}"),
        InlineKeyboardButton(text="⬅️ До ботів", callback_data="pl:my_bots"),
        width=2,
    )
    kb.row(InlineKeyboardButton(text="⬅️ В меню", callback_data="pl:menu"))
    return kb.as_markup()