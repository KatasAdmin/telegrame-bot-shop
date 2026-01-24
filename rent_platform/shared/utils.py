from __future__ import annotations

from typing import Any, Iterable

from aiogram import Bot
from aiogram.types import (
    InlineKeyboardMarkup,
    Message,
    InputMediaPhoto,
)
from aiogram.exceptions import TelegramBadRequest


HTML_PARSE_MODE = "HTML"


async def send_message(
    bot: Bot,
    chat_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    disable_web_page_preview: bool = True,
) -> Message:
    return await bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=HTML_PARSE_MODE,
        reply_markup=reply_markup,
        disable_web_page_preview=disable_web_page_preview,
    )


async def edit_message(
    bot: Bot,
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    disable_web_page_preview: bool = True,
) -> None:
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode=HTML_PARSE_MODE,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview,
        )
    except TelegramBadRequest:
        # Напр. "message is not modified" — не критично
        return


async def safe_delete_message(bot: Bot, chat_id: int, message_id: int) -> None:
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramBadRequest:
        return


async def answer_callback(bot: Bot, callback_query_id: str, text: str = "", show_alert: bool = False) -> None:
    try:
        await bot.answer_callback_query(callback_query_id, text=text, show_alert=show_alert)
    except TelegramBadRequest:
        return


async def send_photo(
    bot: Bot,
    chat_id: int,
    photo: str,
    caption: str = "",
    reply_markup: InlineKeyboardMarkup | None = None,
) -> Message:
    return await bot.send_photo(
        chat_id=chat_id,
        photo=photo,
        caption=caption,
        parse_mode=HTML_PARSE_MODE,
        reply_markup=reply_markup,
    )


async def edit_photo_caption(
    bot: Bot,
    chat_id: int,
    message_id: int,
    caption: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    try:
        await bot.edit_message_caption(
            chat_id=chat_id,
            message_id=message_id,
            caption=caption,
            parse_mode=HTML_PARSE_MODE,
            reply_markup=reply_markup,
        )
    except TelegramBadRequest:
        return


async def edit_message_photo(
    bot: Bot,
    chat_id: int,
    message_id: int,
    photo: str,
    caption: str = "",
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """
    Замінює фото в повідомленні + caption.
    photo: file_id або URL.
    """
    media = InputMediaPhoto(media=photo, caption=caption, parse_mode=HTML_PARSE_MODE)
    try:
        await bot.edit_message_media(
            chat_id=chat_id,
            message_id=message_id,
            media=media,
            reply_markup=reply_markup,
        )
    except TelegramBadRequest:
        return


async def send_media_group_photos(
    bot: Bot,
    chat_id: int,
    photos: Iterable[str],
) -> list[Any]:
    """
    Відправка альбому (фото). Повертає список Message.
    """
    media = [InputMediaPhoto(media=p) for p in photos]
    if not media:
        return []
    return await bot.send_media_group(chat_id=chat_id, media=media)