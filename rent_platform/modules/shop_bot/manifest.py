# rent_platform/modules/shop_bot/manifest.py

MANIFEST = {
    "name": "shop_bot",
    "title": "🛒 Магазин",
    "description": "Повноцінний Telegram-магазин з товарами та замовленнями",
    "version": "1.0.0",
    "price_month": 100,  # грн / місяць (інфо)
    "entry": "rent_platform.modules.shop_bot.router:handle_update",
}