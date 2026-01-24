from __future__ import annotations

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


async def send_or_edit(
    bot: Bot,
    chat_id: int,
    text: str,
    *,
    message_id: int | None,
    kb: InlineKeyboardMarkup | None = None,
) -> int:
    if message_id:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode="HTML",
                reply_markup=kb,
            )
            return int(message_id)
        except Exception:
            pass

    msg = await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=kb)
    return int(msg.message_id)


def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Каталог", callback_data="shop:catalog")],
        [InlineKeyboardButton(text="🛒 Кошик", callback_data="shop:cart")],
        [InlineKeyboardButton(text="⭐️ Обране", callback_data="shop:fav")],
        [InlineKeyboardButton(text="🔥 Хіти/Акції", callback_data="shop:hits")],
        [InlineKeyboardButton(text="🆘 Підтримка", callback_data="shop:support")],
        [InlineKeyboardButton(text="📜 Історія", callback_data="shop:orders")],
    ])


def kb_back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="shop:menu")]
    ])