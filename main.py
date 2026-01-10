import asyncio
import json
import os
import sys
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# -------------------- Переменные окружения --------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID", "0")

print("DEBUG TELEGRAM_TOKEN =", TELEGRAM_TOKEN)
print("DEBUG ADMIN_ID =", ADMIN_ID)

if TELEGRAM_TOKEN is None or TELEGRAM_TOKEN.strip() == "":
    print("❌ ERROR: TELEGRAM_TOKEN не получен из переменных окружения")
    sys.exit(1)

try:
    ADMIN_ID = int(ADMIN_ID)
except ValueError:
    ADMIN_ID = 0

ADMIN_IDS = [ADMIN_ID]

# -------------------- Чистый старт --------------------
def clean_start(token):
    # Удаляем webhook на всякий случай
    try:
        requests.get(f"https://api.telegram.org/bot{token}/deleteWebhook")
        print("✅ Webhook удалён")
    except Exception as e:
        print("❌ Не удалось удалить webhook:", e)

    # Сброс старых getUpdates
    try:
        res = requests.get(f"https://api.telegram.org/bot{token}/getUpdates").json()
        if res.get("result"):
            last_id = res["result"][-1]["update_id"]
            requests.get(f"https://api.telegram.org/bot{token}/getUpdates", params={"offset": last_id + 1})
            print("✅ Сброс старых getUpdates выполнен")
    except Exception as e:
        print("❌ Не удалось сбросить getUpdates:", e)

# Выполняем чистый старт перед инициализацией бота
clean_start(TELEGRAM_TOKEN)

# -------------------- Инициализация бота --------------------
bot = Bot(token=TELEGRAM_TOKEN)
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
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        KeyboardButton("🛍 Каталог"),
        KeyboardButton("🧺 Корзина"),
        KeyboardButton("📦 История заказов"),
        KeyboardButton("📞 Поддержка"),
        KeyboardButton("❤️ Избранное"),
        KeyboardButton("🔍 Поиск")
    )
    return kb

# -------------------- Каталог --------------------
async def show_categories(message):
    if not CATEGORIES:
        await message.answer("Каталог пуст.", reply_markup=main_menu(message.from_user.id))
        return
    kb = InlineKeyboardMarkup()
    for cat in CATEGORIES.keys():
        kb.add(InlineKeyboardButton(cat, callback_data=f"cat_{cat}"))
    kb.add(InlineKeyboardButton("⬅️ Главное меню", callback_data="back_main"))
    await message.answer("Выберите категорию:", reply_markup=kb)

async def show_subcategories(message, category):
    subcats = CATEGORIES.get(category, {})
    if not subcats:
        await message.answer("Нет подкатегорий в этой категории.", reply_markup=main_menu(message.from_user.id))
        return
    kb = InlineKeyboardMarkup()
    for sub in subcats.keys():
        kb.add(InlineKeyboardButton(sub, callback_data=f"sub_{category}_{sub}"))
    kb.add(InlineKeyboardButton("⬅️ Назад к категориям", callback_data="back_categories"))
    await message.answer(f"Подкатегории категории {category}:", reply_markup=kb)

async def show_products(message, category, subcategory):
    products = CATEGORIES.get(category, {}).get(subcategory, [])
    if not products:
        await message.answer("В этой подкатегории пока нет товаров.", reply_markup=main_menu(message.from_user.id))
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
        await message.answer("Ваша корзина пока пуста.", reply_markup=main_menu(user_id))
        return
    text = "Ваша корзина:\n"
    total = 0
    for i, item in enumerate(cart, 1):
        text += f"{i}. {item['name']} — ${item['price']}\n"
        total += item['price']
    text += f"\n💰 Итого: ${total}"
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("💳 Оплатить заказ", callback_data="checkout"))
    kb.add(InlineKeyboardButton("⬅️ Главное меню", callback_data="back_main"))
    await message.answer(text, reply_markup=kb)

# -------------------- История --------------------
async def show_history(message, user_id):
    history = user_history.get(user_id, [])
    if not history:
        await message.answer("История ваших покупок пока пуста.", reply_markup=main_menu(user_id))
        return
    text = "История ваших покупок:\n"
    for i, item in enumerate(history, 1):
        delivery = item.get("address", "Не указано")
        phone = item.get("phone", "Не указан")
        items_list = ', '.join([p['name'] for p in item['items']])
        text += f"{i}. {items_list} — ${item['total']} — Адрес: {delivery} — Телефон: {phone}\n"
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("⬅️ Главное меню", callback_data="back_main"))
    await message.answer(text, reply_markup=kb)

# -------------------- Менеджеры --------------------
async def show_managers(message):
    if not managers:
        await message.answer("Список менеджеров пуст.")
        return
    text = "Менеджеры:\n" + "\n".join([str(m) for m in managers])
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("Добавить менеджера", callback_data="add_manager"))
    kb.add(InlineKeyboardButton("Удалить менеджера", callback_data="remove_manager"))
    kb.add(InlineKeyboardButton("⬅️ Главное меню", callback_data="back_main"))
    await message.answer(text, reply_markup=kb)

# -------------------- Универсальный обработчик сообщений --------------------
@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    text = message.text.strip()
    load_data()

    if text == "/start":
        await message.answer("Привет! Добро пожаловать 👇", reply_markup=main_menu(user_id))
        return

    if text == "🛍 Каталог":
        await show_categories(message)
        return

    if text == "🧺 Корзина":
        await show_cart(message, user_id)
        return

    if text == "📦 История заказов":
        await show_history(message, user_id)
        return

    if text == "📞 Поддержка":
        if not managers:
            await message.answer("Пока нет активных менеджеров.", reply_markup=main_menu(user_id))
            return
        for m_id in managers:
            try:
                await bot.send_message(m_id, f"Пользователь {user_id} просит поддержку")
            except: pass
        await message.answer("Мы уведомили менеджера, ожидайте ответ.", reply_markup=main_menu(user_id))
        return

    if text == "❤️ Избранное":
        await message.answer("Здесь будут ваши любимые товары.", reply_markup=main_menu(user_id))
        return

    if text == "🔍 Поиск":
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("Цена 0-1000", callback_data="price_0_1000"))
        kb.add(InlineKeyboardButton("Цена 1000+", callback_data="price_1000"))
        kb.add(InlineKeyboardButton("⬅️ Главное меню", callback_data="back_main"))
        await message.answer("Выберите фильтр для поиска товаров:", reply_markup=kb)
        return

    await message.answer("Выберите действие из меню:", reply_markup=main_menu(user_id))

# -------------------- Callback --------------------
@dp.callback_query()
async def callback_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = callback.data

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
            await callback.message.answer(f"✅ {name} добавлен(а) в корзину.", reply_markup=main_menu(user_id))
        await callback.answer()
    elif data == "back_main":
        await callback.message.answer("Главное меню:", reply_markup=main_menu(user_id))
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
            await callback.message.answer("Ваша корзина пуста.", reply_markup=main_menu(user_id))
            await callback.answer()
            return
        # Симуляция оплаты
        cart = user_carts.pop(user_id)
        total = sum(item['price'] for item in cart)
        user_history.setdefault(user_id, []).append({
            "items": cart,
            "total": total,
            "address": "Не указано",
            "phone": "Не указан"
        })
        save_data()
        await callback.message.answer(f"✅ Ваш заказ на ${total} оплачен и добавлен в историю!", reply_markup=main_menu(user_id))
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
            await callback.message.answer("Результаты поиска по цене:\n" + "\n".join(results), reply_markup=main_menu(user_id))
        else:
            await callback.message.answer("Товары не найдены по выбранной цене.", reply_markup=main_menu(user_id))
        await callback.answer()

# -------------------- Запуск --------------------
async def main():
    load_data()
    print("🚀 Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())