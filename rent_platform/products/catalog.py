PRODUCT_CATALOG: Dict[str, Dict[str, Any]] = {
    "shop_bot": {
        "title": "🛒 Luna Shop Bot",
        "short": "Магазин-бот (скелет + UI + адмін-додавання товарів)",
        "desc": (
            "🛒 <b>Luna Shop Bot</b>\n\n"
            "Скелет магазину з 6 кнопками, кошиком, обраним та замовленнями.\n"
            "Адмін може додавати категорії/товари командами прямо в боті.\n"
        ),
        "rate_per_min_uah": 0.02,

        # ✅ важливо: module_key == product_key
        "module_key": "shop_bot",

        # ✅ handler можна лишити на modules.shop.router
        "handler": "rent_platform.modules.shop.router:handle_update",
    }
}