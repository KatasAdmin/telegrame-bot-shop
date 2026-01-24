from __future__ import annotations

from aiogram import Bot

from rent_platform.shared.utils import send_message
from rent_platform.modules.luna_shop.ui import (
    main_menu_kb, products_list_kb, product_card_kb, cart_kb, admin_kb
)
from rent_platform.modules.luna_shop.repo import LunaShopRepo


def _extract_msg(update: dict) -> dict | None:
    if update.get("message"):
        return update["message"]
    cb = update.get("callback_query")
    if cb and cb.get("message"):
        return cb["message"]
    return None


def _extract_user_id(update: dict) -> int:
    if update.get("message"):
        return int((update["message"].get("from") or {}).get("id") or 0)
    cb = update.get("callback_query") or {}
    return int((cb.get("from") or {}).get("id") or 0)


def _extract_chat_id(msg: dict) -> int | None:
    cid = (msg.get("chat") or {}).get("id")
    return int(cid) if cid is not None else None


def _text(update: dict) -> str:
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


async def _edit_or_send(bot: Bot, msg: dict, chat_id: int, text: str, reply_markup=None) -> None:
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


def _is_admin(tenant: dict, user_id: int) -> bool:
    return int(tenant.get("owner_user_id") or 0) == int(user_id)


def _uah(kop: int) -> str:
    return f"{int(kop) / 100:.2f}".replace(".00", "")


async def _show_menu(bot: Bot, chat_id: int, is_admin: bool) -> None:
    await bot.send_message(
        chat_id=chat_id,
        text="🛒 <b>Телеграм магазин</b>\nОбери розділ кнопками 👇",
        parse_mode="HTML",
        reply_markup=main_menu_kb(is_admin=is_admin),
    )


async def _show_products(bot: Bot, tenant: dict, tenant_id: str, chat_id: int, user_id: int) -> None:
    products = await LunaShopRepo.list_products(tenant_id)
    is_admin = _is_admin(tenant, user_id)

    if not products:
        if is_admin:
            await bot.send_message(
                chat_id=chat_id,
                text="📦 <b>Каталог порожній</b>\n\nДодай перший товар — і магазин оживе ✅",
                parse_mode="HTML",
                reply_markup=main_menu_kb(is_admin=True),
            )
            await bot.send_message(
                chat_id=chat_id,
                text="🛠 Адміну: швидке додавання\n<b>/a_add_product Назва | 199</b>",
                parse_mode="HTML",
                reply_markup=None,
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text="📦 <b>Каталог поки порожній</b>\n\nСкоро тут зʼявляться товари 🙂",
                parse_mode="HTML",
                reply_markup=main_menu_kb(is_admin=False),
            )
        return

    lines = ["🛍 <b>Каталог</b>\nНатисни ➕ біля товару щоб додати в кошик:"]
    for p in products:
        lines.append(f"• {p['name']} — <b>{_uah(int(p['price_kop']))} грн</b>")

    await bot.send_message(
        chat_id=chat_id,
        text="\n".join(lines),
        parse_mode="HTML",
        reply_markup=products_list_kb(products),
    )


async def _show_hits(bot: Bot, tenant_id: str, chat_id: int, is_admin: bool) -> None:
    # якщо в repo ще нема — тимчасово показуємо пусто красиво
    try:
        products = await LunaShopRepo.list_hits(tenant_id)  # додаси нижче
    except Exception:
        products = []

    if not products:
        await bot.send_message(
            chat_id=chat_id,
            text="🔥 <b>Хіти</b>\n\nПоки що немає хітів 🙂",
            parse_mode="HTML",
            reply_markup=main_menu_kb(is_admin=is_admin),
        )
        return

    lines = ["🔥 <b>Хіти продажу</b>:"]
    for p in products:
        lines.append(f"• {p['name']} — <b>{_uah(int(p['price_kop']))} грн</b>")
    await bot.send_message(chat_id=chat_id, text="\n".join(lines), parse_mode="HTML", reply_markup=products_list_kb(products))


async def _show_sale(bot: Bot, tenant_id: str, chat_id: int, is_admin: bool) -> None:
    try:
        products = await LunaShopRepo.list_sale(tenant_id)  # додаси нижче
    except Exception:
        products = []

    if not products:
        await bot.send_message(
            chat_id=chat_id,
            text="💥 <b>Акції</b>\n\nПоки що немає акційних товарів 🙂",
            parse_mode="HTML",
            reply_markup=main_menu_kb(is_admin=is_admin),
        )
        return

    lines = ["💥 <b>Акції</b>:"]
    for p in products:
        lines.append(f"• {p['name']} — <b>{_uah(int(p['price_kop']))} грн</b>")
    await bot.send_message(chat_id=chat_id, text="\n".join(lines), parse_mode="HTML", reply_markup=products_list_kb(products))


async def _show_favorites(bot: Bot, tenant_id: str, chat_id: int, user_id: int, is_admin: bool) -> None:
    try:
        products = await LunaShopRepo.favorites_list(tenant_id, user_id)  # додаси нижче
    except Exception:
        products = []

    if not products:
        await bot.send_message(
            chat_id=chat_id,
            text="❤️ <b>Обране</b>\n\nТут поки порожньо. Відкрий товар і натисни «❤️ В обране».",
            parse_mode="HTML",
            reply_markup=main_menu_kb(is_admin=is_admin),
        )
        return

    lines = ["❤️ <b>Обране</b>:"]
    for p in products:
        lines.append(f"• {p['name']} — <b>{_uah(int(p['price_kop']))} грн</b>")
    await bot.send_message(chat_id=chat_id, text="\n".join(lines), parse_mode="HTML", reply_markup=products_list_kb(products))


async def _show_cart(bot: Bot, tenant_id: str, chat_id: int, user_id: int, is_admin: bool) -> None:
    items = await LunaShopRepo.cart_list(tenant_id, user_id)
    if not items:
        await bot.send_message(
            chat_id=chat_id,
            text="🛒 <b>Кошик порожній</b>\n\nПерейди в каталог і додай товари.",
            parse_mode="HTML",
            reply_markup=main_menu_kb(is_admin=is_admin),
        )
        return

    total = 0
    lines = ["🛒 <b>Твій кошик</b>:"]
    for it in items:
        s = int(it["price_kop"]) * int(it["qty"])
        total += s
        lines.append(f"• {it['name']} × {it['qty']} = <b>{_uah(s)} грн</b>")

    lines.append(f"\nРазом: <b>{_uah(total)} грн</b>")
    await bot.send_message(
        chat_id=chat_id,
        text="\n".join(lines),
        parse_mode="HTML",
        reply_markup=cart_kb(has_items=True),
    )


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

    # --------- callbacks ----------
    data = _cb_data(update)
    if data.startswith("ls:"):
        try:
            cbq = update.get("callback_query") or {}
            if cbq.get("id"):
                await bot.answer_callback_query(cbq["id"])
        except Exception:
            pass

        parts = data.split(":")
        action = parts[1] if len(parts) > 1 else ""

        if action == "menu":
            await _show_menu(bot, chat_id, is_admin)
            return True

        if action == "products":
            await _show_products(bot, tenant, tenant_id, chat_id, user_id)
            return True

        if action == "cart":
            await _show_cart(bot, tenant_id, chat_id, user_id, is_admin)
            return True

        if action == "cart_clear":
            await LunaShopRepo.cart_clear(tenant_id, user_id)
            await _edit_or_send(bot, msg, chat_id, "🧹 Кошик очищено ✅", reply_markup=None)
            await _show_menu(bot, chat_id, is_admin)
            return True

        if action == "checkout":
            order_id = await LunaShopRepo.create_order_from_cart(tenant_id, user_id)
            if not order_id:
                await _edit_or_send(bot, msg, chat_id, "Кошик порожній 🙂", reply_markup=None)
                await _show_menu(bot, chat_id, is_admin)
                return True
            await _edit_or_send(
                bot, msg, chat_id,
                f"✅ <b>Замовлення #{order_id}</b> створено!\n\nМенеджер скоро звʼяжеться з тобою.",
                reply_markup=None
            )
            await _show_menu(bot, chat_id, is_admin)
            return True

        # favorites toggle
        if action == "fav" and len(parts) >= 3:
            pid = int(parts[2])
            try:
                await LunaShopRepo.favorites_toggle(tenant_id, user_id, pid)  # додаси нижче
                await _edit_or_send(bot, msg, chat_id, "❤️ Ок! Збережено в обраному.", reply_markup=None)
            except Exception:
                await _edit_or_send(bot, msg, chat_id, "Не вийшло додати в обране 😕", reply_markup=None)
            return True

        # add/inc/dec/del товару
        if action in ("add", "inc", "dec", "del"):
            if len(parts) < 3:
                return True
            pid = int(parts[2])

            if action in ("add", "inc"):
                await LunaShopRepo.cart_inc(tenant_id, user_id, pid, +1)
            elif action == "dec":
                await LunaShopRepo.cart_inc(tenant_id, user_id, pid, -1)
            elif action == "del":
                await LunaShopRepo.cart_delete_item(tenant_id, user_id, pid)

            p = await LunaShopRepo.get_product(tenant_id, pid)
            if not p:
                await _edit_or_send(bot, msg, chat_id, "Товар не знайдено або неактивний.", reply_markup=None)
                return True

            await _edit_or_send(
                bot, msg, chat_id,
                f"🧾 <b>{p['name']}</b>\nЦіна: <b>{_uah(int(p['price_kop']))} грн</b>\n\nКерування в кошику:",
                reply_markup=product_card_kb(pid),
            )
            return True

        return True

    # --------- text / commands ----------
    text = _text(update)
    cmd = _normalize_cmd(text)

    # reply keyboard buttons
    if text == "🏠 Меню":
        await _show_menu(bot, chat_id, is_admin)
        return True

    if text == "🛍 Каталог":
        await _show_products(bot, tenant, tenant_id, chat_id, user_id)
        return True

    if text == "🛒 Кошик":
        await _show_cart(bot, tenant_id, chat_id, user_id, is_admin)
        return True

    if text == "🔥 Хіти":
        await _show_hits(bot, tenant_id, chat_id, is_admin)
        return True

    if text == "💥 Акції":
        await _show_sale(bot, tenant_id, chat_id, is_admin)
        return True

    if text == "❤️ Обране":
        await _show_favorites(bot, tenant_id, chat_id, user_id, is_admin)
        return True

    if text == "📦 Замовлення":
        orders = await LunaShopRepo.list_orders(tenant_id, user_id)
        if not orders:
            await bot.send_message(chat_id=chat_id, text="📦 Замовлень ще немає 🙂", parse_mode="HTML", reply_markup=main_menu_kb(is_admin=is_admin))
            return True
        lines = ["📦 <b>Твої замовлення</b>:"]
        for o in orders:
            lines.append(f"• #{o['id']} — {o['status']} — <b>{_uah(int(o['total_kop']))} грн</b>")
        await bot.send_message(chat_id=chat_id, text="\n".join(lines), parse_mode="HTML", reply_markup=main_menu_kb(is_admin=is_admin))
        return True

    if text == "ℹ️ Допомога":
        await bot.send_message(chat_id=chat_id, text="ℹ️ Обирай розділи кнопками. Каталог → додай в кошик → оформити ✅", parse_mode="HTML", reply_markup=main_menu_kb(is_admin=is_admin))
        return True

    if text == "⚙️ Адмінка":
        if not is_admin:
            await send_message(bot, chat_id, "⛔️ Тільки для адміна.")
            return True
        await bot.send_message(chat_id=chat_id, text="🛠 <b>Адмінка</b>\n\nШвидкі дії:", parse_mode="HTML", reply_markup=main_menu_kb(is_admin=True))
        await bot.send_message(chat_id=chat_id, text="• Додати товар: <b>/a_add_product Назва | 199</b>\n(ціна в грн)", parse_mode="HTML", reply_markup=None)
        return True

    # commands
    if cmd in ("/shop", "/start"):
        await _show_menu(bot, chat_id, is_admin)
        return True

    if cmd == "/products":
        await _show_products(bot, tenant, tenant_id, chat_id, user_id)
        return True

    if cmd == "/orders":
        orders = await LunaShopRepo.list_orders(tenant_id, user_id)
        if not orders:
            await send_message(bot, chat_id, "📦 Замовлень ще немає 🙂")
            return True
        lines = ["📦 <b>Твої замовлення</b>:"]
        for o in orders:
            lines.append(f"• #{o['id']} — {o['status']} — <b>{_uah(int(o['total_kop']))} грн</b>")
        await send_message(bot, chat_id, "\n".join(lines))
        return True

    # admin add product
    if cmd == "/a_add_product":
        if not is_admin:
            await send_message(bot, chat_id, "⛔️ Тільки для адміна.")
            return True

        raw = text[len("/a_add_product"):].strip()
        if "|" not in raw:
            await send_message(
                bot, chat_id,
                "Формат:\n<b>/a_add_product Назва товару | 199</b>\nЦіна в грн (ціле число).",
            )
            return True

        name, price = [x.strip() for x in raw.split("|", 1)]
        try:
            price_uah = int(price)
        except Exception:
            await send_message(bot, chat_id, "Ціна має бути числом, наприклад: 199")
            return True

        pid = await LunaShopRepo.add_product(tenant_id, name=name, price_kop=price_uah * 100)
        if not pid:
            await send_message(bot, chat_id, "Не зміг додати товар 😕")
            return True

        await send_message(bot, chat_id, f"✅ Додано товар: <b>{name}</b> (id={pid})")
        return True

    return False