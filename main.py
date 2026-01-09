import asyncio
import json
import os
from aiogram import Bot, Dispatcher, types

# -------------------- Переменные окружения --------------------
# В Railpack переменные из TOML/Env
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID", "0")
try:
    ADMIN_ID = int(ADMIN_ID)
except ValueError:
    ADMIN_ID = 0
ADMIN_IDS = [ADMIN_ID]

# -------------------- Инициализация бота --------------------
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# -------------------- Хранилище --------------------
DATA_FILE = "data.json"
user_carts = {}
user_history = {}
CATEGORIES = {}
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

# -------------------- Универсальный обработчик --------------------
@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    text = message.text.strip()
    load_data()

    if text == "/start":
        await message.answer("Привет! Добро пожаловать 👇", reply_markup=main_menu())
        return

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

    # Оформление заказа
    if user_id in pending_checkout:
        step_data = pending_checkout[user_id]
        if step_data["step"] == "phone":
            if not text.startswith("+380") or len(text) != 13 or not text[1:].isdigit():
                await message.answer("Неверный формат номера. Введите +380XXXXXXXXX")
                return
            step_data["phone"] = text
            step_data["step"] = "address"
            await message.answer("Введите адрес доставки:")
            return
        elif step_data["step"] == "address":
            step_data["address"] = text
            cart = user_carts.get(user_id, [])
            total = sum(i['price'] for i in cart)
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
            await message.answer(f"✅ Заказ оформлен! Сумма: ${total}")
            # уведомление менеджеров
            for m in managers:
                try:
                    text = f"Новый заказ {user_id}:\nТелефон: {order['phone']}\nАдрес: {order['address']}"
                    for idx, item in enumerate(order['items'], 1):
                        text += f"\n{idx}. {item['name']} — ${item['price']}"
                    text += f"\nИтого: ${total}"
                    await bot.send_message(m, text)
                except: pass
            return

    # Меню
    if text == "🛍 Каталог товаров":
        await show_categories(message)
    elif text == "🔥 Акции / Хиты":
        await message.answer("Акции и хиты пока пусты.")
    elif text == "🧺 Моя корзина":
        await show_cart(message, user_id)
    elif text == "📦 История покупок":
        await show_history(message, user_id)
    else:
        await message.answer("Выберите действие из меню:", reply_markup=main_menu())

# -------------------- Callback --------------------
@dp.callback_query()
async def callback_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = callback.data

    if data.startswith("cat_"):
        await show_products(callback.message, data[4:])
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
        await callback.message.answer("Введите номер телефона +380XXXXXXXXX:")
        await callback.answer()

# -------------------- Запуск --------------------
async def main():
    print("Бот запущен...")
    load_data()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())