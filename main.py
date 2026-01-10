import asyncio
import os
import signal
import sys

from aiogram import Bot, Dispatcher, types

# ---------------- ENV ----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not TELEGRAM_TOKEN:
    print("❌ TELEGRAM_TOKEN не задан")
    sys.exit(1)

# ---------------- LOCK ----------------
LOCK_FILE = "/tmp/bot.lock"
if os.path.exists(LOCK_FILE):
    sys.exit(1)

with open(LOCK_FILE, "w") as f:
    f.write("lock")

def shutdown():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)
    sys.exit(0)

signal.signal(signal.SIGTERM, lambda *_: shutdown())
signal.signal(signal.SIGINT, lambda *_: shutdown())

# ---------------- BOT ----------------
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# ---------------- STORAGE ----------------
DATA_FILE = "data.json"
user_carts = {}
user_history = {}
CATEGORIES = {}  # {"Категория": {"Подкатегория": [товары]}}
managers = []

def save_data():
    import json
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "carts": user_carts,
            "history": user_history,
            "categories": CATEGORIES,
            "managers": managers
        }, f, ensure_ascii=False, indent=4)

def load_data():
    import json
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

# ---------------- KEYBOARDS ----------------
def main_menu():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton("🛍 Каталог"), types.KeyboardButton("🧺 Корзина")],
            [types.KeyboardButton("📦 История заказов"), types.KeyboardButton("📞 Поддержка")],
            [types.KeyboardButton("❤️ Избранное"), types.KeyboardButton("🔍 Поиск")]
        ],
        resize_keyboard=True
    )

def back_to_main():
    return types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton("⬅️ Главное меню")]],
        resize_keyboard=True
    )

def search_keyboard():
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton("Цена 0-1000", callback_data="price_0_1000")],
            [types.InlineKeyboardButton("Цена 1000+", callback_data="price_1000")],
            [types.InlineKeyboardButton("⬅️ Главное меню", callback_data="back_main")]
        ]
    )

# ---------------- HANDLERS ----------------
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
            inline_keyboard=[
                [types.InlineKeyboardButton(text=cat, callback_data=f"cat_{cat}")]
                for cat in CATEGORIES.keys()
            ]
        )
        await message.answer("Выберите категорию:", reply_markup=kb)
        return

    if text == "🧺 Корзина":
        cart = user_carts.get(user_id, [])
        if not cart:
            await message.answer("Корзина пуста.", reply_markup=main_menu())
            return
        total = sum(item["price"] for item in cart)
        text_lines = "\n".join(f"{i+1}. {p['name']} — ${p['price']}" for i, p in enumerate(cart))
        await message.answer(f"{text_lines}\n\n💰 Итого: ${total}", reply_markup=back_to_main())
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
            await message.answer("Пока нет активных менеджеров.", reply_markup=main_menu())
            return
        for m in managers:
            try:
                await bot.send_message(m, f"Пользователь {user_id} просит поддержку")
            except: pass
        await message.answer("Мы уведомили менеджера.", reply_markup=main_menu())
        return

    if text == "🔍 Поиск":
        await message.answer("Выберите фильтр:", reply_markup=search_keyboard())
        return

    await message.answer("Выберите действие из меню 👇", reply_markup=main_menu())

# ---------------- CALLBACKS ----------------
@dp.callback_query()
async def callbacks(cb: types.CallbackQuery):
    user_id = str(cb.from_user.id)
    data = cb.data
    load_data()

    if data == "back_main":
        await cb.message.answer("Главное меню:", reply_markup=main_menu())
        await cb.answer()
        return

    if data.startswith("cat_"):
        cat = data[4:]
        subs = CATEGORIES.get(cat, {})
        kb = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text=sub, callback_data=f"sub_{cat}_{sub}")]
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
            kb = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton("🛒 В корзину", callback_data=f"buy_{cat}_{sub}_{p['name']}")]
                ]
            )
            await cb.message.answer(f"{p['name']}\n${p['price']}\n{p['description']}", reply_markup=kb)
        await cb.answer()
        return

    if data.startswith("buy_"):
        _, cat, sub, name = data.split("_", 3)
        product = next(p for p in CATEGORIES[cat][sub] if p["name"] == name)
        user_carts.setdefault(user_id, []).append(product)
        save_data()
        await cb.message.answer("Добавлено в корзину ✅", reply_markup=main_menu())
        await cb.answer()

# ---------------- START ----------------
async def main():
    load_data()
    print("🚀 Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())