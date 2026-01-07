import asyncio
import json
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# -------------------- Конфигурация --------------------
BOT_TOKEN = "8278813878:AAFUHXC5K1vrBZ6zrUKILn7qRWAm33y6AUk" # Твой токен бота
ADMIN_ID = 8385663990 # Твой Telegram ID
MANAGER_ID = 8266881584 # ID менеджера
ADMIN_IDS = [ADMIN_ID] # Список админов

# -------------------- Инициализация --------------------
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# -------------------- Файловое хранилище --------------------
DATA_FILE = "data.json"
user_carts = {}
user_history = {}
CATEGORIES = {}
pending_admin = {}
pending_checkout = {}

def save_data():
with open(DATA_FILE, "w", encoding="utf-8") as f:
json.dump({
"carts": user_carts,
"history": user_history,
"categories": CATEGORIES
}, f, ensure_ascii=False, indent=4)

def load_data():
global user_carts, user_history, CATEGORIES
if os.path.exists(DATA_FILE):
try:
with open(DATA_FILE, "r", encoding="utf-8") as f:
data = json.load(f)
user_carts = data.get("carts", {})
user_history = data.get("history", {})
CATEGORIES = data.get("categories", {})
except json.JSONDecodeError:
user_carts = {}
user_history = {}
CATEGORIES = {}
save_data()
else:
user_carts = {}
user_history = {}
CATEGORIES = {}
save_data()

# -------------------- Главное меню --------------------
def main_menu():
keyboard = types.ReplyKeyboardMarkup(
keyboard=[
[types.KeyboardButton("🛍 Каталог товаров"), types.KeyboardButton("🔥 Акции / Хиты")],
[types.KeyboardButton("🧺 Моя корзина"), types.KeyboardButton("📦 История покупок")],
[types.KeyboardButton("❤️ Избранное"), types.KeyboardButton("📞 Поддержка")]
],
resize_keyboard=True
)
return keyboard

# -------------------- Пользовательский старт --------------------
@dp.message(Command("start"))
async def start(message: types.Message):
load_data()
await message.answer("Привет! Добро пожаловать в магазин 👇\nВыберите действие:", reply_markup=main_menu())

# -------------------- Меню пользователя --------------------
@dp.message()
async def menu_handler(message: types.Message):
user_id = message.from_user.id
text = message.text

if text == "/admin" and user_id in ADMIN_IDS:
await show_admin_menu(message)
return

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
elif text == "📞 Поддержка":
await message.answer("Свяжитесь с поддержкой: @твой_username")
else:
await message.answer("Выберите действие из меню ниже.", reply_markup=main_menu())

# -------------------- Пользовательские функции --------------------
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

# -------------------- Корзина и оформление заказа --------------------
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

# -------------------- Шаги оформления заказа --------------------
@dp.callback_query()
async def callback_handler(callback: types.CallbackQuery):
user_id = callback.from_user.id
data = callback.data

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
elif data.startswith("admin_"):
action = data.split("_")[1]
pending_admin[user_id] = {"action": action, "step": "category"}
await callback.message.answer(f"Вы выбрали {action}. Введите категорию товара:")
await callback.answer()

# -------------------- Обработка ввода телефона и адреса --------------------
@dp.message()
async def checkout_steps(message: types.Message):
user_id = message.from_user.id
if user_id not in pending_checkout:
return

step_data = pending_checkout[user_id]
text = message.text.strip()

if step_data["step"] == "phone":
if not text.startswith("+380") or not text[1:].isdigit() or len(text) != 13:
await message.answer("Неверный формат номера. Введите снова в формате +380XXXXXXXXX:")
return
step_data["phone"] = text
step_data["step"] = "address"
await message.answer("Введите адрес доставки:")

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

await message.answer(f"✅ Заказ успешно оформлен!\nСумма: ${total}\nНомер: {order['phone']}\nАдрес: {order['address']}")

manager_text = f"Новый заказ от пользователя {user_id}:\nТелефон: {order['phone']}\nАдрес: {order['address']}\n"
for i, item in enumerate(order['items'], 1):
manager_text += f"{i}. {item['name']} — ${item['price']}\n"
manager_text += f"Итого: ${total}"
try:
await bot.send_message(MANAGER_ID, manager_text)
except Exception as e:
print(f"Ошибка при отправке менеджеру: {e}")

# -------------------- История покупок --------------------
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
kb.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))
await message.answer("Меню администратора:", reply_markup=kb)

# -------------------- Шаги админа --------------------
@dp.message()
async def admin_steps(message: types.Message):
user_id = message.from_user.id
if user_id not in pending_admin:
return
data = message.text.strip()
admin_state = pending_admin[user_id]
action = admin_state["action"]

if admin_state["step"] == "category":
admin_state["category"] = data
if action == "add":
admin_state["step"] = "name"
await message.answer("Введите название товара:")
elif action in ["edit", "delete"]:
if data not in CATEGORIES:
await message.answer("Категория не найдена. Попробуйте снова.")
return
admin_state["step"] = "choose_product"
kb = types.InlineKeyboardMarkup()
for prod in CATEGORIES[data]:
kb.add(types.InlineKeyboardButton(prod["name"], callback_data=f"admin_product_{prod['name']}"))
await message.answer("Выберите товар:", reply_markup=kb)

elif admin_state["step"] == "name":
admin_state["name"] = data
admin_state["step"] = "price"
await message.answer("Введите цену товара:")

elif admin_state["step"] == "price":
try:
admin_state["price"] = float(data)
admin_state["step"] = "description"
await message.answer("Введите описание товара:")
except ValueError:
await message.answer("Неверная цена, введите число:")

elif admin_state["step"] == "description":
admin_state["description"] = data
admin_state["step"] = "photo"
await message.answer("Введите URL фото товара:")

elif admin_state["step"] == "photo":
admin_state["photo"] = data
cat = admin_state["category"]
if cat not in CATEGORIES:
CATEGORIES[cat] = []
CATEGORIES[cat].append({
"name": admin_state["name"],
"price": admin_state["price"],
"description": admin_state["description"],
"photo": admin_state["photo"]
})
save_data()
await message.answer(f"✅ Товар {admin_state['name']} добавлен в категорию {cat}.")
pending_admin.pop(user_id)

# -------------------- Запуск --------------------
async def main():
print("Бот запущен...")
load_data()
await dp.start_polling(bot)

if __name__ == "__main__":
asyncio.run(main())
