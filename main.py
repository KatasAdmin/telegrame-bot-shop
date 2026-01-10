import asyncio
import json
import os

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode


# ================== НАСТРОЙКИ ==================

BOT_TOKEN = os.getenv("BOT_TOKEN") or "PASTE_YOUR_TOKEN_HERE"
DATA_FILE = "data.json"


# ================== BOT / DISPATCHER ==================

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()


# ================== ХРАНИЛИЩЕ ==================

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}, "orders": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


data = load_data()


def get_user(user_id: int):
    user_id = str(user_id)
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "cart": [],
            "history": []
        }
        save_data(data)
    return data["users"][user_id]


# ================== КЛАВИАТУРЫ ==================

main_menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🛍 Каталог"), KeyboardButton(text="🧺 Корзина")],
        [KeyboardButton(text="📦 История заказов")],
        [KeyboardButton(text="📞 Поддержка")]
    ],
    resize_keyboard=True
)


def catalog_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👟 Обувь", callback_data="cat_shoes")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
        ]
    )


def shoes_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Nike Air", callback_data="item_nike")],
            [InlineKeyboardButton(text="Adidas Run", callback_data="item_adidas")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_catalog")]
        ]
    )


def item_kb(item_id: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ В корзину", callback_data=f"add_{item_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_shoes")]
        ]
    )


def cart_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Оформить заказ", callback_data="checkout")],
            [InlineKeyboardButton(text="🗑 Очистить корзину", callback_data="clear_cart")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
        ]
    )


# ================== START ==================

@dp.message(CommandStart())
async def start(message: Message):
    get_user(message.from_user.id)
    await message.answer(
        "👋 Добро пожаловать в магазин!\n\nВыберите действие:",
        reply_markup=main_menu_kb
    )


# ================== МЕНЮ ==================

@dp.message(F.text == "🛍 Каталог")
async def open_catalog(message: Message):
    await message.answer("📂 Каталог товаров:", reply_markup=catalog_kb())


@dp.message(F.text == "🧺 Корзина")
async def open_cart(message: Message):
    user = get_user(message.from_user.id)

    if not user["cart"]:
        await message.answer("🧺 Корзина пуста")
        return

    text = "🧺 <b>Ваша корзина:</b>\n"
    for item in user["cart"]:
        text += f"• {item}\n"

    await message.answer(text, reply_markup=cart_kb())


@dp.message(F.text == "📦 История заказов")
async def order_history(message: Message):
    user = get_user(message.from_user.id)

    if not user["history"]:
        await message.answer("📦 История заказов пуста")
        return

    text = "📦 <b>Ваши заказы:</b>\n"
    for order in user["history"]:
        text += f"• {order}\n"

    await message.answer(text)


@dp.message(F.text == "📞 Поддержка")
async def support(message: Message):
    await message.answer("📞 Поддержка:\nНапишите сюда @support")
    # ================== CALLBACKS ==================

@dp.callback_query(F.data == "cat_shoes")
async def open_shoes(callback: CallbackQuery):
    await callback.message.edit_text(
        "👟 Обувь:",
        reply_markup=shoes_kb()
    )
    await callback.answer()


@dp.callback_query(F.data == "back_catalog")
async def back_to_catalog(callback: CallbackQuery):
    await callback.message.edit_text(
        "📂 Каталог товаров:",
        reply_markup=catalog_kb()
    )
    await callback.answer()


@dp.callback_query(F.data == "back_shoes")
async def back_to_shoes(callback: CallbackQuery):
    await callback.message.edit_text(
        "👟 Обувь:",
        reply_markup=shoes_kb()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("item_"))
async def item_view(callback: CallbackQuery):
    item_id = callback.data.replace("item_", "")

    items = {
        "nike": "👟 Nike Air — 120$",
        "adidas": "👟 Adidas Run — 95$"
    }

    await callback.message.edit_text(
        items.get(item_id, "Товар не найден"),
        reply_markup=item_kb(item_id)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("add_"))
async def add_to_cart(callback: CallbackQuery):
    item_id = callback.data.replace("add_", "")
    user = get_user(callback.from_user.id)

    user["cart"].append(item_id)
    save_data(data)

    await callback.message.answer(
        "✅ Товар добавлен в корзину",
        reply_markup=main_menu_kb
    )
    await callback.answer()


@dp.callback_query(F.data == "clear_cart")
async def clear_cart(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    user["cart"].clear()
    save_data(data)

    await callback.message.answer("🗑 Корзина очищена")
    await callback.answer()


@dp.callback_query(F.data == "checkout")
async def checkout(callback: CallbackQuery):
    user = get_user(callback.from_user.id)

    if not user["cart"]:
        await callback.message.answer("❌ Корзина пуста")
        await callback.answer()
        return

    order_text = ", ".join(user["cart"])
    user["history"].append(order_text)
    user["cart"].clear()

    data["orders"].append({
        "user": callback.from_user.id,
        "items": order_text
    })

    save_data(data)

    await callback.message.answer(
        "✅ Заказ оформлен!\nСпасибо за покупку 🎉",
        reply_markup=main_menu_kb
    )
    await callback.answer()


@dp.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    await callback.message.answer(
        "🏠 Главное меню:",
        reply_markup=main_menu_kb
    )
    await callback.answer()


# ================== ЗАПУСК ==================

async def main():
    print("🚀 Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())