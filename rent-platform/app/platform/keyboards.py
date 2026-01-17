# app/platform/keyboards.py
from __future__ import annotations

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import types


def platform_home_kb() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🛒 Маркетплейс ботів", callback_data="pf:market")
    kb.button(text="⚙️ Мої боти (оренда)", callback_data="pf:mybots")
    kb.button(text="👤 Профіль", callback_data="pf:profile")
    kb.button(text="💳 Оплата / Тарифи", callback_data="pf:billing")  # поки заглушка
    kb.adjust(1)
    return kb.as_markup()


def back_home_kb() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="pf:home")
    kb.adjust(1)
    return kb.as_markup()


def mybots_kb() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Додати бот (токен)", callback_data="pf:tenant:add")
    kb.button(text="🧩 Підключити модуль", callback_data="pf:tenant:modules")
    kb.button(text="👥 Доступи (адміни/менеджери)", callback_data="pf:tenant:staff")
    kb.button(text="⬅️ Назад", callback_data="pf:home")
    kb.adjust(1)
    return kb.as_markup()


def market_kb() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🛍 Магазин-бот", callback_data="pf:market:shop")
    kb.button(text="📈 Інвест-бот", callback_data="pf:market:invest")
    kb.button(text="💼 Фріланс-бот", callback_data="pf:market:freelance")
    kb.button(text="⬅️ Назад", callback_data="pf:home")
    kb.adjust(1)
    return kb.as_markup()