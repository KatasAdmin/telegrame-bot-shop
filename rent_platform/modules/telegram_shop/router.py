from __future__ import annotations

import time
from typing import Any

from aiogram import Bot

from rent_platform.modules.telegram_shop.ui.user_kb import user_main_kb, back_to_menu_kb
from rent_platform.modules.telegram_shop.repo.products import ProductsRepo
from rent_platform.modules.telegram_shop.repo.cart import CartRepo
from rent_platform.shared.utils import send_message


# ---------- update helpers ----------
def _extract_msg(update: dict) -> dict | None:
    if update.get("message"):
        return update["message"]
    cb = update.get("callback_query")
    if cb and cb.get("message"):
        return cb["message"]
    return None


def _extract_chat_id(msg: dict) -> int | None:
    cid = (msg.get("chat") or {}).get("id")
    return int(cid) if cid is not None else None


def _extract_user_id(update: dict) -> int:
    if update.get("message"):
        return int(((update["message"].get("from") or {}).get("id")) or 0)
    cb = update.get("callback_query") or {}
    return int(((cb.get("from") or {}).get("id")) or 0)


def _extract_text(update: dict) -> str:
    msg = update.get("message") or {}
    return (msg.get("text") or "").strip()


def _normalize_cmd(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    first = t.split(maxsplit=1)[0]
    if "@" in first:
        first = first.split("@", 1)[0]
    return first


def _cb_data(update: dict) -> str:
    cb = update.get("callback_query") or {}
    return (cb.get("data") or "").strip()


def _is_admin(tenant: dict, user_id: int) -> bool:
    return int(tenant.get("owner_user_id") or 0) == int(user_id)


def _uah(kop: int) -> str:
    return f"{int(kop) / 100:.2f}".replace(".00", "")


async def _answer_cb(bot: Bot, update: dict) -> None:
    try:
        cbq = update.get("callback_query") or {}
        if cbq.get("id"):
            await bot.answer_callback_query(cbq["id"])
    except Exception:
        pass


# ---------- screens ----------
async def _show_menu(bot: Bot, chat_id: int) -> None:
    await bot.send_message(
        chat_id=chat_id,
        text="🛒 <b>Телеграм магазин</b>\nОбирай розділ кнопками 👇",
        parse_mode="HTML",
        reply_markup=user_main_kb(),
    )


async def _show_catalog(bot: Bot, tenant_id: str, chat_id: int) -> None:
    products = await ProductsRepo.list_products(tenant_id)
    if not products:
        await bot.send_message(
            chat_id=chat_id,
            text="📦 <b>Товарів ще немає</b>\n\nАдмін додасть їх у панелі керування 🙂",
            parse_mode="HTML",
            reply_markup=back_to_menu_kb(),
        )
        return

    lines: list[str] = ["🛍 <b>Каталог</b>:"]
    for p in products:
        lines.append(f"• {p['name']} — <b>{_uah(int(p['price_kop']))} грн</b>")

    await bot.send_message(
        chat_id=chat_id,
        text="\n".join(lines),
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(),
    )


async def _show_cart(bot: Bot, tenant_id: str, chat_id: int, user_id: int) -> None:
    items = await CartRepo.list_items(tenant_id, user_id)
    if not items:
        await bot.send_message(
            chat_id=chat_id,
            text="🛒 <b>Кошик порожній</b>\n\nЗайди в каталог і додай товари.",
            parse_mode="HTML",
            reply_markup=back_to_menu_kb(),
        )
        return

    total = 0
    lines: list[str] = ["🛒 <b>Твій кошик</b>:"]
    for it in items:
        s = int(it["price_kop"]) * int(it["qty"])
        total += s
        lines.append(f"• {it['name']} × {it['qty']} = <b>{_uah(s)} грн</b>")

    lines.append(f"\nРазом: <b>{_uah(total)} грн</b>")

    await bot.send_message(
        chat_id=chat_id,
        text="\n".join(lines),
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(),
    )


# ---------- main handler ----------
async def handle_update(tenant: dict, update: dict, bot: Bot) -> bool:
    msg = _extract_msg(update)
    if not msg:
        return False

    chat_id = _extract_chat_id(msg)
    if not chat_id:
        return False

    tenant_id = str(tenant.get("id") or tenant.get("tenant_id") or "")
    user_id = _extract_user_id(update)

    # callbacks (поки мінімально — просто прибираємо "loading")
    data = _cb_data(update)
    if data:
        await _answer_cb(bot, update)
        return False  # поки інлайн не робимо, тільки reply-кнопки

    text = _extract_text(update)
    cmd = _normalize_cmd(text)

    # старт / меню
    if cmd in ("/start", "/shop"):
        await _show_menu(bot, chat_id)
        return True

    # reply кнопки
    if text == "🏠 Меню":
        await _show_menu(bot, chat_id)
        return True

    if text == "🛍 Каталог":
        await _show_catalog(bot, tenant_id, chat_id)
        return True

    if text == "🛒 Кошик":
        await _show_cart(bot, tenant_id, chat_id, user_id)
        return True

    if text == "ℹ️ Допомога":
        await bot.send_message(
            chat_id=chat_id,
            text="ℹ️ Обирай розділи кнопками.\nКаталог → додай в кошик → оформлення ✅ (скоро).",
            parse_mode="HTML",
            reply_markup=back_to_menu_kb(),
        )
        return True

    # адмін (поки просто заглушка, щоб юзерам не мозолило)
    if cmd == "/a_help":
        if not _is_admin(tenant, user_id):
            await send_message(bot, chat_id, "⛔️ Тільки для адміна.")
            return True
        await send_message(
            bot,
            chat_id,
            "🛠 <b>Адмін-панель</b>\n"
            "Скоро додамо команди: товари/категорії/акції/хіти ✅",
        )
        return True

    return False