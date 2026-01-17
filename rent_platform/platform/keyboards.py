from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


# === Тексти кнопок (одним місцем, щоб потім легко міняти/локалізувати/кастомізувати під тенанта) ===
BTN_MARKETPLACE = "🧩 Маркетплейс"
BTN_MY_BOTS = "🤖 Мої боти"
BTN_CABINET = "👤 Кабінет"
BTN_PARTNERS = "🤝 Партнери"
BTN_HELP = "🆘 Підтримка"

BTN_ADMIN = "🛠 Адмінка (скоро)"  # на майбутнє (для тебе/команди)


def main_menu_kb(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """
    Головне меню платформи.
    is_admin залишили — потім прив'яжемо до ролей/менеджерів.
    """
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
    """
    Inline-версія меню (на випадок, якщо юзер не любить reply клавіатуру).
    """
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
    kb.row(
        InlineKeyboardButton(text=BTN_HELP, callback_data="pl:support"),
        width=1,
    )
    return kb.as_markup()


def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ В меню", callback_data="pl:menu")]]
    )


def partners_inline_kb() -> InlineKeyboardMarkup:
    """
    Під-меню Партнерів (рефка, правила, виплати) — одразу структура на майбутнє.
    """
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
    """
    Загальна інформація: політика, умови, зобов'язання — буде корисно і для Telegram (Privacy Policy URL).
    """
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
    """
    items: [{"id": "...", "name": "..."}]
    """
    kb = InlineKeyboardBuilder()
    for it in items:
        bot_id = it["id"]
        name = it.get("name") or "Bot"
        kb.row(
            InlineKeyboardButton(text=f"🗑 {name}", callback_data=f"pl:my_bots:del:{bot_id}")
        )
    kb.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="pl:my_bots"), width=1)
    return kb.as_markup()
