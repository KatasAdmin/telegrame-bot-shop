# rent_platform/modules/shop/manifest.py

MANIFEST = {
    "name": "shop",
    "title": "🛒 Магазин",
    "description": "Повноцінний Telegram-магазин з товарами та замовленнями",
    "version": "1.0.0",
    "price_month": 100,  # грн / місяць
    "entry": "rent_platform.modules.shop.router:handle_update",
}