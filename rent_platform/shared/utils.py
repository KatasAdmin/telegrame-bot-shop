# rent_platform/shared/utils.py
from __future__ import annotations

from aiogram import Bot


async def send_message(
    bot_or_token: Bot | str,
    chat_id: int,
    text: str,
    *,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True,
) -> None:
    """
    Універсальна відправка повідомлення.
    - bot_or_token: або готовий aiogram.Bot, або token (str)
    """
    if isinstance(bot_or_token, Bot):
        bot = bot_or_token
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
        )
        return

    # fallback: якщо передали токен
    bot = Bot(token=bot_or_token)
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
        )
    finally:
        await bot.session.close()