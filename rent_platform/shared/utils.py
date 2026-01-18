from __future__ import annotations

import httpx
from aiogram import Bot


async def send_message(bot: Bot, chat_id: int, text: str) -> None:
    # aiogram method (краще ніж руками через httpx)
    await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")