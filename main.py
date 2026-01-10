import asyncio
import json
import os
import sys
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# -------------------- Переменные окружения --------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID", "0")

print("DEBUG BOT_TOKEN =", BOT_TOKEN)
print("DEBUG ADMIN_ID =", ADMIN_ID)

if BOT_TOKEN is None or BOT_TOKEN.strip() == "":
    print("❌ ERROR: BOT_TOKEN не получен из переменных окружения")
    sys.exit(1)

try:
    ADMIN_ID = int(ADMIN_ID)
except ValueError:
    ADMIN_ID = 0

ADMIN_IDS = [ADMIN_ID]

# -------------------- Инициализация бота --------------------
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# -------------------- Хранилище --------------------
DATA_FILE = "data.json"
user_carts = {}
user_history = {}
CATEGORIES = {}  # {"Категория": {"Подкатегория": [товары]}}
pending_checkout = {}
managers = []

SUPPORT_MESSAGE = "Пользователь хочет связаться с поддержкой."

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
            CATEGORIES = data.get("categories", {})
            managers = data.get("managers", [])
        except json.JSONDecodeError:
            user_carts, user_history, CATEGORIES, managers = {}, {}, {}, []
            save_data()
    else:
        user_carts, user_history, CATEGORIES, managers = {}, {}, {}, []
        save_data()

# -------------------- Главное меню --------------------
def main_menu(user_id):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    if user_id in ADMIN_IDS:
        kb.add(KeyboardButton("🛍 Каталог товаров"), KeyboardButton("🔥 Акции / Хиты"))
        kb.add(KeyboardButton("🧺 Моя корзина"), KeyboardButton("📦 История покупок"))
        kb.add(KeyboardButton("👨‍💼 Менеджеры"), KeyboardButton("📞 Поддержка"))
        kb.add(KeyboardButton("📊 Статистика"), KeyboardButton("⚙️ Управление товарами"))
    elif user_id in managers:
        kb.add(KeyboardButton("🛍 Каталог товаров"), KeyboardButton("🔥 Акции / Хиты"))
        kb.add(KeyboardButton("🧺 Моя корзина"), KeyboardButton("📦 История покупок"))
        kb.add(KeyboardButton("📞 Поддержка"), KeyboardButton("📊 Заказы"))
    else:
        kb.add(KeyboardButton("🛍 Каталог товаров"), KeyboardButton("🔥 Акции / Хиты"))
        kb.add(KeyboardButton("🧺 Моя корзина"), KeyboardButton("📦 История покупок"))
        kb.add(KeyboardButton("❤️ Избранное"), KeyboardButton("📞 Поддержка"))
    return kb

# -------------------- Каталог --------------------
async def show_categories(message):
    if not CATEGORIES:
        await message.answer("Каталог пуст.")
        return
    kb = InlineKeyboardMarkup()
    for cat in CATEGORIES.keys():
        kb.add(InlineKeyboardButton(cat, callback_data=f"cat_{cat}"))
    kb.add(InlineKeyboardButton("Поиск по цене 0-1000", callback_data="price_0_1000"))
    kb.add(InlineKeyboardButton("Поиск по цене 1000+", callback_data="price_1000"))
    await message.answer("Выберите категорию:", reply_markup=kb)

async def show_subcategories(message, category):
    subcats = CATEGORIES.get(category, {})
    if not subcats:
        await message.answer("Нет подкатегорий в этой категории.")
        return
    kb = InlineKeyboardMarkup()
    for sub in subcats.keys():
        kb.add(InlineKeyboardButton(sub, callback_data=f"sub_{category}_{sub}"))
    kb.add(InlineKeyboardButton("⬅️ Назад к категориям", callback_data="back_categories"))
    await message.answer(f"Подкатегории категории {category}:", reply_markup=kb)

async def show_products(message, category, subcategory):
    products = CATEGORIES.get(category, {}).get(subcategory, [])
    if not products:
        await message.answer("В этой подкатегории пока нет товаров.")
        return
    for prod in products:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🛒 В корзину", callback_data=f"prod_{category}_{subcategory}_{prod['name']}"))
        kb.add(InlineKeyboardButton("⬅️ Назад", callback_data=f"back_sub_{category}"))
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=prod.get("photo", ""),
            caption=f"{prod['name']}\nЦена: ${prod['price']}\n{prod['description']}",
            reply_markup=kb
        )

# -------------------- Корзина --------------------
async def show_cart(message, user_id):
    cart = user_carts.get(user_id, [])
    if not cart:
        await message.answer("Ваша корзина пока пуста.")
        return
    text = "Ваша корзина:\n"
    total = 0
    for i, item in enumerate(cart, 1):
        text += f"{i}. {item['name']} — ${item['price']}\n"
        total += item['price']
    text += f"\n💰 Итого: ${total}"
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("💳 Оплатить заказ", callback_data="checkout"))
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_categories"))
    await message.answer(text, reply_markup=kb)

# -------------------- История --------------------
async def show_history(message, user_id):
    history = user_history.get(user_id, [])
    if not history:
        await message.answer("История ваших покупок пока пуста.")
        return
    text = "Ваша история покупок:\n"
    for i, item in enumerate(history, 1):
        delivery = item.get("address", "Не указано")
        phone = item.get("phone", "Не указан")
        text += f"{i}. {', '.join([p['name'] for p in item['items']])} — ${item['total']} — Адрес: {delivery} — Телефон: {phone}\n"
    await message.answer(text)

# -------------------- Менеджеры --------------------
async def show_managers(message):
    if not managers:
        await message.answer("Список менеджеров пуст.")
        return
    text = "Менеджеры:\n" + "\n".join([str(m) for m in managers])
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("Добавить менеджера", callback_data="add_manager"))
    kb.add(InlineKeyboardButton("Удалить менеджера", callback_data="remove_manager"))
    await message.answer(text, reply_markup=kb)

# -------------------- Универсальный обработчик --------------------
@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    text = message.text.strip()
    load_data()

    # -------------------- Старт --------------------
    if text == "/start":
        await message.answer("Привет! Добро пожаловать 👇", reply_markup=main_menu(user_id))
        return

    # -------------------- Поддержка --------------------
    if text == "📞 Поддержка":
        if not managers:
            await message.answer("Пока нет активных менеджеров.")
            return
        for m_id in managers:
            try:
                await bot.send_message(m_id, f"{SUPPORT_MESSAGE}\nПользователь: {user_id}")
            except: pass
        await message.answer("Мы уведомили менеджера, ожидайте ответ.")
        return

    # -------------------- Менеджеры --------------------
    if text == "👨‍💼 Менеджеры" and user_id in ADMIN_IDS:
        await show_managers(message)
        return

    # -------------------- Управление товарами --------------------
    if text == "⚙️ Управление товарами" and user_id in ADMIN_IDS:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("Добавить категорию", callback_data="add_category"))
        kb.add(InlineKeyboardButton("Редактировать категорию", callback_data="edit_category"))
        kb.add(InlineKeyboardButton("Удалить категорию", callback_data="remove_category"))
        await message.answer("Управление товарами:", reply_markup=kb)
        return

    # -------------------- Корзина и история --------------------
    if text == "🧺 Моя корзина":
        await show_cart(message, user_id)
        return
    if text == "📦 История покупок":
        await show_history(message, user_id)
        return

    # -------------------- Каталог --------------------
    if text == "🛍 Каталог товаров":
        await show_categories(message)
        return
    if text == "🔥 Акции / Хиты":
        await message.answer("Акции и хиты пока пусты.")
        return

    await message.answer("Выберите действие из меню:", reply_markup=main_menu(user_id))

# -------------------- Callback --------------------
@dp.callback_query()
async def callback_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = callback.data

    # -------------------- Категории --------------------
    if data.startswith("cat_"):
        category = data[4:]
        await show_subcategories(callback.message, category)
        await callback.answer()
    elif data.startswith("sub_"):
        parts = data.split("_")
        category = parts[1]
        subcategory = "_".join(parts[2:])
        await show_products(callback.message, category, subcategory)
        await callback.answer()
    elif data.startswith("prod_"):
        parts = data.split("_")
        category = parts[1]
        subcategory = parts[2]
        name = "_".join(parts[3:])
        product = next((p for p in CATEGORIES[category][subcategory] if p["name"] == name), None)
        if product:
            user_carts.setdefault(user_id, []).append(product)
            save_data()
            await callback.message.answer(f"✅ {name} добавлен(а) в корзину.")
        await callback.answer()
    elif data == "back_categories":
        await show_categories(callback.message)
        await callback.answer()
    elif data.startswith("back_sub_"):
        category = data[9:]
        await show_subcategories(callback.message, category)
        await callback.answer()
    elif data == "checkout":
        if not user_carts.get(user_id):
            await callback.message.answer("Ваша корзина пуста.")
            await callback.answer()
            return
        pending_checkout[user_id] = {"step": "phone"}
        await callback.message.answer("Введите номер телефона +380XXXXXXXXX:")
        await callback.answer()
    elif data.startswith("price_"):
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
            await callback.message.answer("Результаты поиска по цене:\n" + "\n".join(results))
        else:
            await callback.message.answer("Товары не найдены по выбранной цене.")
        await callback.answer()

# -------------------- Запуск --------------------
async def main():
    load_data()
    print("🚀 Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())