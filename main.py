import asyncio
import json
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv

# -------------------- Загрузка переменных окружения --------------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
ADMIN_IDS = [ADMIN_ID]

# -------------------- Инициализация бота --------------------
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# -------------------- Хранилище --------------------
DATA_FILE = "data.json"
user_carts = {}
user_history = {}
CATEGORIES = {}
pending_admin = {}
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
            user_carts = {}
            user_history = {}
            CATEGORIES = {}
            managers = []
            save_data()
    else:
        user_carts = {}
        user_history = {}
        CATEGORIES = {}
        managers = []
        save_data()

# -------------------- Главное меню --------------------
def main_menu():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton("🛍 Каталог товаров"), types.KeyboardButton("🔥 Акции / Хиты")],
            [types.KeyboardButton("🧺 Моя корзина"), types.KeyboardButton("📦 История покупок")],
            [types.KeyboardButton("❤️ Избранное"), types.KeyboardButton("📞 Поддержка")]
        ],
        resize_keyboard=True
    )

# -------------------- Каталог --------------------
async def show_categories(message):
    if not CATEGORIES:
        await message.answer("Каталог пуст.")
        return
    kb = types.InlineKeyboardMarkup()
    for cat in CATEGORIES.keys():
        kb.add(types.InlineKeyboardButton(cat, callback_data=f"cat_{cat}"))
    await message.answer("Выберите категорию:", reply_markup=kb)

async def show_products(message, category):
    products = CATEGORIES.get(category, [])
    for prod in products:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🛒 В корзину", callback_data=f"prod_{category}_{prod['name']}"))
        kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_categories"))
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
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("💳 Оплатить заказ", callback_data="checkout"))
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_categories"))
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

# -------------------- Админ-панель --------------------
async def show_admin_menu(message):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("➕ Добавить товар", callback_data="admin_add"))
    kb.add(types.InlineKeyboardButton("✏️ Редактировать товар", callback_data="admin_edit"))
    kb.add(types.InlineKeyboardButton("❌ Удалить товар", callback_data="admin_delete"))
    kb.add(types.InlineKeyboardButton("👤 Управление менеджерами", callback_data="admin_managers"))
    kb.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))
    await message.answer("Меню администратора:", reply_markup=kb)

# -------------------- Управление менеджерами --------------------
async def show_managers_menu(message):
    kb = types.InlineKeyboardMarkup()
    if managers:
        for m_id in managers:
            kb.add(types.InlineKeyboardButton(f"❌ {m_id}", callback_data=f"remove_manager_{m_id}"))
    kb.add(types.InlineKeyboardButton("➕ Добавить менеджера", callback_data="add_manager"))
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_back"))
    await message.answer("Список менеджеров:", reply_markup=kb)

# -------------------- Универсальный обработчик сообщений --------------------
@dp.message()
async def all_messages(message: types.Message):
    user_id = message.from_user.id
    text = message.text.strip()

    # Старт
    if text == "/start":
        load_data()
        await message.answer("Привет! Добро пожаловать в магазин 👇\nВыберите действие:", reply_markup=main_menu())
        return

    # Поддержка
    if text == "📞 Поддержка":
        if not managers:
            await message.answer("Пока нет активных менеджеров, попробуйте позже.")
            return
        for m_id in managers:
            try:
                await bot.send_message(m_id, f"{SUPPORT_MESSAGE}\nПользователь: {user_id}")
            except Exception as e:
                print(f"Ошибка при отправке менеджеру {m_id}: {e}")
        await message.answer("Мы уведомили менеджера, ожидайте ответ.")
        return

    # Шаги оформления заказа
    if user_id in pending_checkout:
        step_data = pending_checkout[user_id]
        if step_data["step"] == "phone":
            if not text.startswith("+380") or not text[1:].isdigit() or len(text) != 13:
                await message.answer("Неверный формат номера. Введите снова в формате +380XXXXXXXXX:")
                return
            step_data["phone"] = text
            step_data["step"] = "address"
            await message.answer("Введите адрес доставки:")
            return
        elif step_data["step"] == "address":
            step_data["address"] = text
            cart = user_carts.get(user_id, [])
            total = sum(item['price'] for item in cart)
            order = {
                "items": cart.copy(),
                "total": total,
                "phone": step_data["phone"],
                "address": step_data["address"],
                "status": "Оплачен"
            }
            user_history.setdefault(user_id, []).append(order)
            user_carts[user_id] = []
            save_data()
            pending_checkout.pop(user_id)
            await message.answer(
                f"✅ Заказ успешно оформлен!\nСумма: ${total}\nНомер: {order['phone']}\nАдрес: {order['address']}"
            )
            # Отправка всем менеджерам
            manager_text = f"Новый заказ от пользователя {user_id}:\nТелефон: {order['phone']}\nАдрес: {order['address']}\n"
            for i, item in enumerate(order['items'], 1):
                manager_text += f"{i}. {item['name']} — ${item['price']}\n"
            manager_text += f"Итого: ${total}"
            for m in managers:
                try:
                    await bot.send_message(m, manager_text)
                except Exception as e:
                    print(f"Ошибка при отправке менеджеру {m}: {e}")
            return

    # Меню пользователя
    if text == "🛍 Каталог товаров":
        await show_categories(message)
    elif text == "🔥 Акции / Хиты":
        await message.answer("Вы открыли акции и хиты!")
    elif text == "🧺 Моя корзина":
        await show_cart(message, user_id)
    elif text == "📦 История покупок":
        await show_history(message, user_id)
    elif text == "❤️ Избранное":
        await message.answer("Ваш список избранного пока пуст.")
    else:
        await message.answer("Выберите действие из меню ниже.", reply_markup=main_menu())

# -------------------- Callback Handler --------------------
@dp.callback_query()
async def callback_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = callback.data

    # --- Категории и товары ---
    if data.startswith("cat_"):
        category = data[4:]
        await show_products(callback.message, category)
        await callback.answer()
    elif data.startswith("prod_"):
        parts = data.split("_")
        category = parts[1]
        name = "_".join(parts[2:])
        product = next((p for p in CATEGORIES[category] if p["name"] == name), None)
        if product:
            user_carts.setdefault(user_id, []).append(product)
            save_data()
            await callback.message.answer(f"✅ {name} добавлен(а) в корзину.")
        await callback.answer()
    elif data == "back_categories":
        await show_categories(callback.message)
        await callback.answer()
    elif data == "checkout":
        if not user_carts.get(user_id):
            await callback.message.answer("Ваша корзина пуста.")
            await callback.answer()
            return
        pending_checkout[user_id] = {"step": "phone"}
        await callback.message.answer("Введите ваш номер телефона в формате +380XXXXXXXXX:")
        await callback.answer()

    # --- Админ ---
    elif data.startswith("admin_"):
        action = data.split("_")[1]
        if action == "managers":
            await show_managers_menu(callback.message)
        elif action == "add_manager":
            pending_admin[user_id] = {"action": "add_manager", "step": "enter_id"}
            await callback.message.answer("Введите Telegram ID нового менеджера:")
        await callback.answer()
    
    # --- Менеджеры ---
    elif data.startswith("remove_manager_"):
        remove_id = int(data.split("_")[2])
        if remove_id in managers:
            managers.remove(remove_id)
            save_data()
            await callback.message.answer(f"❌ Менеджер {remove_id} удален.")
        await show_managers_menu(callback.message)
        await callback.answer()
    elif data == "admin_back":
        await show_admin_menu(callback.message)
        await callback.answer()

# -------------------- Запуск --------------------
async def main():
    print("Бот запущен...")
    load_data()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())