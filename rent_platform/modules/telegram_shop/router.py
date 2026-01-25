from __future__ import annotations

from aiogram import Bot

from rent_platform.shared.utils import send_message
from rent_platform.modules.telegram_shop.ui import (
    main_menu_kb,
    catalog_kb,
    product_card_kb,
)
from rent_platform.modules.telegram_shop.repo.products import ProductsRepo


# ----------------- helpers -----------------

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


def _text(update: dict) -> str:
    msg = update.get("message") or {}
    return (msg.get("text") or "").strip()


def _cb_data(update: dict) -> str:
    cb = update.get("callback_query") or {}
    return (cb.get("data") or "").strip()


def _normalize_cmd(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    first = t.split(maxsplit=1)[0]
    if "@" in first:
        first = first.split("@", 1)[0]
    return first


def _is_admin(tenant: dict, user_id: int) -> bool:
    return int(tenant.get("owner_user_id") or 0) == int(user_id)


def _uah(kop: int) -> str:
    return f"{int(kop) / 100:.2f}".replace(".00", "")


async def _edit_or_send(bot: Bot, msg: dict, chat_id: int, text: str, reply_markup=None) -> None:
    """
    Для callback зручно редагувати те ж повідомлення.
    Якщо не вийшло — просто надсилаємо нове.
    """
    try:
        mid = msg.get("message_id")
        if mid and reply_markup is not None:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=int(mid),
                text=text,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
            return
    except Exception:
        pass

    await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=reply_markup)


async def _answer_cb(bot: Bot, update: dict) -> None:
    try:
        cbq = update.get("callback_query") or {}
        if cbq.get("id"):
            await bot.answer_callback_query(cbq["id"])
    except Exception:
        pass


# ----------------- screens -----------------

async def _show_menu(bot: Bot, chat_id: int, is_admin: bool) -> None:
    await bot.send_message(
        chat_id=chat_id,
        text="🛒 <b>Телеграм магазин</b>\nОбери розділ кнопками 👇",
        parse_mode="HTML",
        reply_markup=main_menu_kb(is_admin=is_admin),
    )


async def _show_catalog(bot: Bot, tenant_id: str, chat_id: int, is_admin: bool) -> None:
    products = await ProductsRepo.list(tenant_id)
    if not products:
        # НІЯКИХ інструкцій для юзера, тільки норм текст
        txt = "📦 <b>Каталог порожній</b>\n\nСкоро додамо товари 🙂"
        # але адмінові покажемо коротко як додати
        if is_admin:
            txt += "\n\n🛠 Для додавання:\n<b>/a_add_product Назва | 199</b>\n(ціна в грн)"
        await bot.send_message(
            chat_id=chat_id,
            text=txt,
            parse_mode="HTML",
            reply_markup=main_menu_kb(is_admin=is_admin),
        )
        return

    lines = ["🛍 <b>Каталог</b>\nНатисни на товар щоб відкрити картку:"]
    for p in products:
        lines.append(f"• {p['name']} — <b>{_uah(int(p['price_kop']))} грн</b>")

    await bot.send_message(
        chat_id=chat_id,
        text="\n".join(lines),
        parse_mode="HTML",
        reply_markup=catalog_kb(products),
    )


async def _show_product(bot: Bot, msg: dict, chat_id: int, tenant_id: str, product_id: int) -> None:
    p = await ProductsRepo.get(tenant_id, product_id)
    if not p:
        await _edit_or_send(bot, msg, chat_id, "Товар не знайдено або він неактивний 🙃", reply_markup=None)
        return

    await _edit_or_send(
        bot,
        msg,
        chat_id,
        f"🧾 <b>{p['name']}</b>\nЦіна: <b>{_uah(int(p['price_kop']))} грн</b>",
        reply_markup=product_card_kb(int(p["id"])),
    )


# ----------------- main handler -----------------

async def handle_update(tenant: dict, update: dict, bot: Bot) -> bool:
    msg = _extract_msg(update)
    if not msg:
        return False

    chat_id = _extract_chat_id(msg)
    if not chat_id:
        return False

    tenant_id = str(tenant.get("id") or tenant.get("tenant_id") or "")
    user_id = _extract_user_id(update)
    is_admin = _is_admin(tenant, user_id)

    # -------- callbacks --------
    data = _cb_data(update)
    if data.startswith("ts:"):
        await _answer_cb(bot, update)

        # формат: ts:action[:id]
        parts = data.split(":")
        action = parts[1] if len(parts) > 1 else ""
        pid = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0

        if action == "menu":
            await _edit_or_send(bot, msg, chat_id, "🏠 Меню", reply_markup=None)
            await _show_menu(bot, chat_id, is_admin=is_admin)
            return True

        if action == "catalog":
            await _edit_or_send(bot, msg, chat_id, "🛍 Відкриваю каталог…", reply_markup=None)
            await _show_catalog(bot, tenant_id, chat_id, is_admin=is_admin)
            return True

        if action == "product" and pid:
            await _show_product(bot, msg, chat_id, tenant_id, pid)
            return True

        return True

    # -------- text / buttons / commands --------
    text = _text(update)
    cmd = _normalize_cmd(text)

    # меню кнопками
    if text in ("🏠 Меню",):
        await _show_menu(bot, chat_id, is_admin=is_admin)
        return True

    if text in ("🛍 Каталог",):
        await _show_catalog(bot, tenant_id, chat_id, is_admin=is_admin)
        return True

    if text in ("ℹ️ Допомога",):
        # коротко, без “введіть команду”
        await bot.send_message(
            chat_id=chat_id,
            text="ℹ️ Обирай розділи кнопками. Каталог → відкрий товар → далі буде кошик/оформлення ✅",
            parse_mode="HTML",
            reply_markup=main_menu_kb(is_admin=is_admin),
        )
        return True

    if text in ("🛠 Адмін",):
        if not is_admin:
            await send_message(bot, chat_id, "⛔️ Тільки для адміна.")
            return True
        await bot.send_message(
            chat_id=chat_id,
            text=(
                "🛠 <b>Адмін-панель</b>\n\n"
                "Поки що швидко через команду:\n"
                "<b>/a_add_product Назва | 199</b>\n"
                "(ціна в грн)\n\n"
                "Далі зробимо адмінку кнопками ✅"
            ),
            parse_mode="HTML",
            reply_markup=main_menu_kb(is_admin=True),
        )
        return True

    # базові команди (підтримка, якщо хтось все ж введе)
    if cmd in ("/start", "/shop"):
        await _show_menu(bot, chat_id, is_admin=is_admin)
        return True

    if cmd == "/products":
        await _show_catalog(bot, tenant_id, chat_id, is_admin=is_admin)
        return True

    # admin: /a_add_product Назва | 199
    if cmd == "/a_add_product":
        if not is_admin:
            await send_message(bot, chat_id, "⛔️ Тільки для адміна.")
            return True

        raw = text[len("/a_add_product"):].strip()
        if "|" not in raw:
            await send_message(
                bot,
                chat_id,
                "Формат:\n<b>/a_add_product Назва товару | 199</b>\nЦіна в грн (ціле число).",
            )
            return True

        name, price = [x.strip() for x in raw.split("|", 1)]
        try:
            price_uah = int(price)
        except Exception:
            await send_message(bot, chat_id, "Ціна має бути числом, наприклад: 199")
            return True

        pid = await ProductsRepo.add(tenant_id, name=name, price_kop=price_uah * 100)
        if not pid:
            await send_message(bot, chat_id, "Не зміг додати товар 😕")
            return True

        await send_message(bot, chat_id, f"✅ Додано товар: <b>{name}</b> (id={pid})")
        return True

    return False