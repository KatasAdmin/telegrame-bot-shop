# rent_platform/platform/handlers/start.py
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router()


@router.message(CommandStart())
async def start_cmd(m: Message):
    await m.answer("✅ Rent Platform запущено.\n\nДалі буде маркетплейс модулів і оренда 😏🚀")