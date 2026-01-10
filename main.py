import asyncio
import json
import os
import signal
import sys
from aiogram import Bot, Dispatcher, types

# -------------------- ПЕРЕМЕННЫЕ --------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or "ВАШ_ТОКЕН_СЮДА"
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not TELEGRAM_TOKEN:
    print("❌ TELEGRAM_TOKEN не задан")
    sys.exit(1)

# -------------------- ЗАЩИТА ОТ ДВОЙНОГО ЗАПУСКА --------------------
LOCK_FILE = "/tmp/bot.lock"
if os.path.exists(LOCK_FILE):
    print("❌ Бот уже запущен")
    sys.exit(1)

with open(LOCK_FILE, "w") as f:
    f.write("lock")

def shutdown():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)
    print("🛑 Бот остановлен")
    sys.exit(0)

signal.signal(signal.SIGTERM, lambda *_: shutdown())
signal.signal(signal.SIGINT, lambda *_: shutdown())

# -------------------- ИНИЦИАЛИЗАЦИЯ --------------------
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# -------------------- ХРАНИЛИЩЕ --------------------
DATA_FILE = "data.json"
user_carts = {}
user_history = {}
CATEGORIES = {
    "Электроника": {
        "Телефоны": [
            {"name": "iPhone 14", "price": 999, "description": "Смартфон Apple", "photo": "https://via.placeholder.com/300"},
            {"name": "Samsung S23", "price": 899, "description": "Смартфон Samsung", "photo": "https://via.placeholder.com/300"}
        ],
        "Ноутбуки": [
            {"name": "MacBook Pro", "price": 1999, "description": "Ноутбук Apple", "photo": "https://via.placeholder.com/300"},
            {"name": "Dell XPS", "price": 1499, "description": "Ноутбук Dell", "photo": "https://via.placeholder.com/300"}
        ]
    },
    "Одежда": {
        "Футболки": [
            {"name": "Футболка Nike", "price": 49, "description": "Спортивная футболка", "photo": "https://via.placeholder.com/300"}
        ]
    }
}
managers = []

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "carts": user_carts,
            "history": user_history,
            "categories": CATEGORIES,
            "managers": managers
        }, f, ensure_ascii=False, indent=4)

def load_data():
    global user_carts, user_history, CATEGORIES, managers
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            user_carts = data.get("carts", {})
            user_history = data.get("history", {})
            CATEGORIES = data.get("categories", CATEGORIES)
            managers = data.get("managers", [])
        except json.JSONDecodeError:
            save_data()
    else:
        save_data()

# -------------------- КЛАВИАТУРЫ --------------------
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        types.KeyboardButton("🛍 Каталог"),
        types.KeyboardButton("🧺 Корзина"),
        types.KeyboardButton("📦 История заказов"),
        types.KeyboardButton("📞 Поддержка"),
        types.KeyboardButton("❤️ Избранное"),
        types.KeyboardButton("🔍 Поиск")
    )
    return kb

def back_to_main():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("⬅️ Главное меню"))
    return kb

def search_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Цена 0-1000", callback_data="price_0_1000"))
    kb.add(types.InlineKeyboardButton("Цена 1000+", callback_data="price_1000"))
    kb.add(types.InlineKeyboardButton("⬅️ Главное меню", callback_data="back_main"))
    return kb

# -------------------- ОБРАБОТЧИКИ --------------------
@dp.message()
async def handle_message(message: types.Message):
    text = (message.text or "").strip()
    user_id = str(message.from_user.id)
    load_data()

    if text == "/start":
        await message.answer("Привет! Добро пожаловать 👇", reply_markup=main_menu())
        return

    if text == "🛍 Каталог":
        if not CATEGORIES:
            await message.answer("Каталог пуст.")
            return
        kb = types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(cat, callback_data=f"cat_{cat}")] for cat in CATEGORIES]
        )
        await message.answer("Выберите категорию:", reply_markup=kb)
        return

    if text == "🧺 Корзина":
        cart = user_carts.get(user_id, [])
        if not cart:
            await message.answer("Корзина пуста.", reply_markup=main_menu())
            return
        total = sum(item["price"] for item in cart)
        text_cart = "\n".join(f"{i+1}. {p['name']} — ${p['price']}" for i, p in enumerate(cart))
        await message.answer(f"{text_cart}\n\n💰 Итого: ${total}", reply_markup=back_to_main())
        return

    if text == "📦 История заказов":
        history = user_history.get(user_id, [])
        if not history:
            await message.answer("История пуста.", reply_markup=main_menu())
            return
        lines = []
        for i, order in enumerate(history, 1):
            items = ", ".join(p["name"] for p in order["items"])
            lines.append(f"{i}. {items} — ${order['total']}")
        await message.answer("\n".join(lines), reply_markup=main_menu())
        return

    if text == "📞 Поддержка":
        if not managers:
            await message.answer("Пока нет менеджеров.", reply_markup=main_menu())
            return
        for m in managers:
            await bot.send_message(m, f"Пользователь {user_id} просит поддержку")
        await message.answer("Мы уведомили менеджера.", reply_markup=main_menu())
        return

    if text == "🔍 Поиск":
        await message.answer("Выберите фильтр:", reply_markup=search_keyboard())
        return

    await message.answer("Выберите действие из меню 👇", reply_markup=main_menu())

# -------------------- CALLBACK --------------------
@dp.callback_query()
async def callbacks(cb: types.CallbackQuery):
    user_id = str(cb.from_user.id)
    data = cb.data

    if data == "back_main":
        await cb.message.answer("Главное меню:", reply_markup=main_menu())
        await cb.answer()
        return

    if data.startswith("cat_"):
        cat = data[4:]
        subs = CATEGORIES.get(cat, {})
        kb = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(sub, callback_data=f"sub_{cat}_{sub}")]
                for sub in subs
            ] + [[types.InlineKeyboardButton("⬅️ Назад", callback_data="back_main")]]
        )
        await cb.message.answer("Подкатегории:", reply_markup=kb)
        await cb.answer()
        return

    if data.startswith("sub_"):
        _, cat, sub = data.split("_", 2)
        products = CATEGORIES.get(cat, {}).get(sub, [])
        for p in products:
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("🛒 В корзину", callback_data=f"buy_{cat}_{sub}_{p['name']}"))
            await cb.message.answer_photo(photo=p['photo'], caption=f"{p['name']}\n${p['price']}\n{p['description']}", reply_markup=kb)
        await cb.answer()
        return

    if data.startswith("buy_"):
        _, cat, sub, name = data.split("_", 3)
        product = next(p for p in CATEGORIES[cat][sub] if p["name"] == name)
        user_carts.setdefault(user_id, []).append(product)
        save_data()
        await cb.message.answer("Добавлено в корзину ✅", reply_markup=main_menu())
        await cb.answer()

    if data.startswith("price_"):
        max_price = 1000 if data == "price_0_1000" else None
        results = []
        for cat, subs in CATEGORIES.items():
            for sub, items in subs.items():
                for p in items:
                    if max_price is None and p["price"] > 1000:
                        results.append(f"{p['name']} — ${p['price']}")
                    elif max_price is not None and p["price"] <= 1000:
                        results.append(f"{p['name']} — ${p['price']}")
        if results:
            await cb.message.answer("Результаты поиска:\n" + "\n".join(results), reply_markup=main_menu())
        else:
            await cb.message.answer("Товары не найдены.", reply_markup=main_menu())
        await cb.answer()

# -------------------- ЗАПУСК --------------------
async def main():
    load_data()
    print("🚀 Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())