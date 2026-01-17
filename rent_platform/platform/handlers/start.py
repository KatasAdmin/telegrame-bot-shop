# rent_platform/platform/handlers/start.py

from fastapi import APIRouter

router = APIRouter()


@router.get("/start")
async def platform_start():
    return {
        "message": "👋 Ласкаво просимо до платформи оренди ботів",
        "actions": [
            "Орендувати бота",
            "Мої боти",
            "Налаштування"
        ]
    }