# rent_platform/shared/utils.py
from __future__ import annotations

import logging
from typing import Optional

from aiogram import Bot

log = logging.getLogger(__name__)


async def send_message(
    bot: Bot,
    chat_id: int,
    text: str,
    *,
    parse_mode: Optional[str] = None,
    disable_web_page_preview: bool = True,
) -> None:
    """
    Універсальна відправка повідомлень для модулів.
    Працює і для platform bot, і для tenant bot (потрібно передати відповідний Bot).
    """
    await bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=parse_mode,
        disable_web_page_preview=disable_web_page_preview,
    )