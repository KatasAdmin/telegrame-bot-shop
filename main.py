import asyncio
import os
import signal
import sys

from aiogram import Bot, Dispatcher, types

from keyboards import main_menu, back_to_main, search_keyboard
from storage import (
    load_data,
    save_data,
    user_carts,
    user_history,
    CATEGORIES,
    managers,
)

# ---------------- ENV ----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not TELEGRAM_TOKEN or TELEGRAM_TOKEN.strip() == "":
    print("❌ TELEGRAM_TOKEN не задан!")
    sys.exit(1)

# ---------------- LOCK ----------------
LOCK_FILE = "/tmp/bot.lock"
if os.path.exists(LOCK_FILE):
    print("❌ Бот уже запущен")
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
bot = Bot(token=TELEGRAM_TOKEN, parse_mode=types.ParseMode.HTML)
dp = Dispatcher()

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
        lines = "\n".join(f"{i+1}. {p['name']} — ${p['price']}" for i, p in enumerate(cart))
        await message.answer(f"{lines}\n\n💰 Итого: ${total}", reply_markup=back_to_main())
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
        for m_id in managers:
            try:
                await bot.send_message(m_id, f"Пользователь {user_id} просит поддержку")
            except Exception:
                continue
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

    # Назад в главное меню
    if data == "back_main":
        await cb.message.answer("Главное меню:", reply_markup=main_menu())
        await cb.answer()
        return

    # Категория -> подкатегории
    if data.startswith("cat_"):
        cat = data[4:]
        subs = CATEGORIES.get(cat, {})
        if not subs:
            await cb.message.answer("В этой категории нет подкатегорий.", reply_markup=main_menu())
            await cb.answer()
            return
        kb = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text=sub, callback_data=f"sub_{cat}_{sub}")]
                for sub in subs
            ]
            + [[types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]]
        )
        await cb.message.answer("Выберите подкатегорию:", reply_markup=kb)
        await cb.answer()
        return

    # Подкатегория -> товары
    if data.startswith("sub_"):
        _, cat, sub = data.split("_", 2)
        products = CATEGORIES.get(cat, {}).get(sub, [])
        if not products:
            await cb.message.answer("В этой подкатегории пока нет товаров.", reply_markup=main_menu())
            await cb.answer()
            return
        for p in products:
            kb = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text="🛒 В корзину", callback_data=f"buy_{cat}_{sub}_{p['name']}")],
                    [types.InlineKeyboardButton(text="⬅️ Назад", callback_data=f"cat_{cat}")]
                ]
            )
            await cb.message.answer(
                f"{p['name']}\nЦена: ${p['price']}\n{p.get('description', '')}",
                reply_markup=kb,
            )
        await cb.answer()
        return

    # Добавление товара в корзину
    if data.startswith("buy_"):
        _, cat, sub, name = data.split("_", 3)
        product = next((p for p in CATEGORIES.get(cat, {}).get(sub, []) if p["name"] == name), None)
        if not product:
            await cb.message.answer("Ошибка добавления в корзину.", reply_markup=main_menu())
            await cb.answer()
            return
        user_carts.setdefault(user_id, []).append(product)
        save_data()
        await cb.message.answer(f"✅ {name} добавлен(а) в корзину.", reply_markup=main_menu())
        await cb.answer()
        return

# ---------------- START ----------------
async def main():
    load_data()
    print("🚀 Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        shutdown()