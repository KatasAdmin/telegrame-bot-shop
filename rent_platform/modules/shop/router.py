from __future__ import annotations

from typing import Any

from aiogram import Bot

from rent_platform.modules.shop.storage import (
    get_shop_db,
    cart_get,
    fav_get,
    cart_total_uah,
    make_order_from_cart,
)
from rent_platform.modules.shop.ui import (
    kb_home,
    kb_back_home,
    kb_categories,
    kb_product,
    kb_cart,
    kb_cart_item,
    kb_favorites,
    kb_hot,
)
from rent_platform.shared.utils import (
    send_message,
    edit_message,
    send_photo,
    edit_message_photo,
    edit_photo_caption,
    answer_callback,
)


def _u(update: dict) -> dict | None:
    return update.get("message") or update.get("callback_query") or None


def _get_user_id(update: dict) -> int | None:
    cq = update.get("callback_query")
    if cq:
        u = cq.get("from") or {}
        return u.get("id")
    msg = update.get("message")
    if msg:
        u = msg.get("from") or {}
        return u.get("id")
    return None


def _get_chat_id(update: dict) -> int | None:
    cq = update.get("callback_query")
    if cq:
        msg = cq.get("message") or {}
        chat = msg.get("chat") or {}
        return chat.get("id")
    msg = update.get("message")
    if msg:
        chat = msg.get("chat") or {}
        return chat.get("id")
    return None


def _get_message_id_from_update(update: dict) -> int | None:
    cq = update.get("callback_query")
    if cq:
        msg = cq.get("message") or {}
        return msg.get("message_id")
    msg = update.get("message")
    if msg:
        return msg.get("message_id")
    return None


async def _render(
    *,
    bot: Bot,
    db,
    user_id: int,
    chat_id: int,
    text: str,
    reply_markup,
    photo: str | None = None,
) -> None:
    """
    “Один екран = одне повідомлення”.
    Якщо раніше вже було UI message_id — редагуємо.
    Якщо нема — надсилаємо і запам’ятовуємо.
    """
    mid = db.ui_message_id.get(int(user_id))

    if mid:
        if photo:
            await edit_message_photo(bot, chat_id, mid, photo, caption=text, reply_markup=reply_markup)
        else:
            await edit_message(bot, chat_id, mid, text=text, reply_markup=reply_markup)
        return

    # перший рендер
    if photo:
        m = await send_photo(bot, chat_id, photo=photo, caption=text, reply_markup=reply_markup)
    else:
        m = await send_message(bot, chat_id, text=text, reply_markup=reply_markup)

    db.ui_message_id[int(user_id)] = int(m.message_id)


def _fmt_price(price_uah: int, old_price_uah: int = 0) -> str:
    if old_price_uah and old_price_uah > price_uah:
        return f"<b>{price_uah} грн</b>  <s>{old_price_uah} грн</s>"
    return f"<b>{price_uah} грн</b>"


async def handle_update(tenant: dict, update: dict[str, Any], bot: Bot) -> bool:
    msg = update.get("message")
    cq = update.get("callback_query")

    user_id = _get_user_id(update)
    chat_id = _get_chat_id(update)
    if not user_id or not chat_id:
        return False

    db = get_shop_db(tenant["id"])

    # =========================
    # TEXT COMMANDS
    # =========================
    if msg:
        text = (msg.get("text") or "").strip()

        if text in ("/start", "/shop"):
            await _render(
                bot=bot, db=db, user_id=user_id, chat_id=chat_id,
                text="🛒 <b>Магазин</b>\nОбирай розділ:",
                reply_markup=kb_home(),
                photo=None,
            )
            return True

        # швидкі команди (для дебага)
        if text == "/products":
            return await _handle_cb(tenant, bot, db, user_id, chat_id, "shop:catalog", cq_id=None)
        if text == "/cart":
            return await _handle_cb(tenant, bot, db, user_id, chat_id, "shop:cart", cq_id=None)

        return False

    # =========================
    # CALLBACKS
    # =========================
    if cq:
        data = (cq.get("data") or "").strip()
        cq_id = cq.get("id") or ""
        return await _handle_cb(tenant, bot, db, user_id, chat_id, data, cq_id=cq_id)

    return False


async def _handle_cb(tenant: dict, bot: Bot, db, user_id: int, chat_id: int, data: str, cq_id: str | None) -> bool:
    if data == "noop":
        if cq_id:
            await answer_callback(bot, cq_id, "")
        return True

    if not data.startswith("shop:"):
        return False

    if cq_id:
        await answer_callback(bot, cq_id, "")

    parts = data.split(":")
    # shop:<action>...
    action = parts[1] if len(parts) > 1 else "home"

    # ---------- HOME ----------
    if action == "home":
        await _render(
            bot=bot, db=db, user_id=user_id, chat_id=chat_id,
            text="🛒 <b>Магазин</b>\nОбирай розділ:",
            reply_markup=kb_home(),
        )
        return True

    # ---------- CATALOG ----------
    if action == "catalog":
        await _render(
            bot=bot, db=db, user_id=user_id, chat_id=chat_id,
            text="📦 <b>Каталог</b>\nВибери категорію:",
            reply_markup=kb_categories(db),
        )
        return True

    if action == "cat" and len(parts) >= 3:
        cat_id = parts[2]
        # список товарів "картками": ми робимо одну картку за раз.
        # Поки — просто перший доступний товар + кнопка назад у каталог.
        prods = [p for p in db.products.values() if p.enabled and p.category_id == cat_id]
        if not prods:
            await _render(
                bot=bot, db=db, user_id=user_id, chat_id=chat_id,
                text="В цій категорії поки немає товарів 😅",
                reply_markup=kb_categories(db),
            )
            return True

        # покажемо перший; далі зробимо paging
        p = prods[0]
        fav = fav_get(db, user_id)
        in_fav = p.id in fav

        text = (
            f"🧾 <b>{p.title}</b>\n"
            f"{_fmt_price(p.price_uah, p.old_price_uah)}\n\n"
            f"{p.desc}"
        )
        photo = p.photos[0] if p.photos else None

        await _render(
            bot=bot, db=db, user_id=user_id, chat_id=chat_id,
            text=text,
            reply_markup=kb_product(p.id, in_fav=in_fav),
            photo=photo,
        )
        return True

    # ---------- PRODUCT OPEN ----------
    if action == "prod" and len(parts) >= 3:
        pid = parts[2]
        p = db.products.get(pid)
        if not p or not p.enabled:
            await _render(
                bot=bot, db=db, user_id=user_id, chat_id=chat_id,
                text="Товар не знайдено або вимкнений.",
                reply_markup=kb_back_home(),
            )
            return True

        fav = fav_get(db, user_id)
        in_fav = pid in fav

        text = (
            f"🧾 <b>{p.title}</b>\n"
            f"{_fmt_price(p.price_uah, p.old_price_uah)}\n\n"
            f"{p.desc}"
        )
        photo = p.photos[0] if p.photos else None

        await _render(
            bot=bot, db=db, user_id=user_id, chat_id=chat_id,
            text=text,
            reply_markup=kb_product(pid, in_fav=in_fav),
            photo=photo,
        )
        return True

    # ---------- FAVORITES ----------
    if action == "fav":
        # shop:fav
        if len(parts) == 2:
            await _render(
                bot=bot, db=db, user_id=user_id, chat_id=chat_id,
                text="⭐ <b>Обране</b>",
                reply_markup=kb_favorites(db, user_id),
            )
            return True

        # shop:fav:add:<pid> / shop:fav:del:<pid>
        if len(parts) >= 4:
            sub = parts[2]
            pid = parts[3]
            fav = fav_get(db, user_id)
            if sub == "add":
                fav[pid] = 1
            elif sub == "del":
                fav.pop(pid, None)

            # перерендерим товар (якщо відкритий)
            p = db.products.get(pid)
            if p and p.enabled:
                in_fav = pid in fav
                text = (
                    f"🧾 <b>{p.title}</b>\n"
                    f"{_fmt_price(p.price_uah, p.old_price_uah)}\n\n"
                    f"{p.desc}"
                )
                photo = p.photos[0] if p.photos else None
                await _render(
                    bot=bot, db=db, user_id=user_id, chat_id=chat_id,
                    text=text,
                    reply_markup=kb_product(pid, in_fav=in_fav),
                    photo=photo,
                )
            else:
                await _render(
                    bot=bot, db=db, user_id=user_id, chat_id=chat_id,
                    text="⭐ <b>Обране</b>",
                    reply_markup=kb_favorites(db, user_id),
                )
            return True

    # ---------- CART ----------
    if action == "cart":
        # shop:cart
        if len(parts) == 2:
            total = cart_total_uah(db, user_id)
            text = f"🧺 <b>Кошик</b>\n\nРазом: <b>{total} грн</b>"
            await _render(
                bot=bot, db=db, user_id=user_id, chat_id=chat_id,
                text=text,
                reply_markup=kb_cart(db, user_id),
            )
            return True

        # shop:cart:add:<pid>
        if len(parts) >= 4 and parts[2] == "add":
            pid = parts[3]
            cart = cart_get(db, user_id)
            it = cart.get(pid)
            if it:
                it.qty += 1
            else:
                cart[pid] = type(next(iter(cart.values()), None)) or None  # not used
                cart[pid] = __import__("rent_platform.modules.shop.storage", fromlist=["CartItem"]).CartItem(product_id=pid, qty=1)

            total = cart_total_uah(db, user_id)
            await _render(
                bot=bot, db=db, user_id=user_id, chat_id=chat_id,
                text=f"✅ Додано в кошик.\n\n🧺 Разом: <b>{total} грн</b>",
                reply_markup=kb_cart(db, user_id),
            )
            return True

        # shop:cart:item:<pid>
        if len(parts) >= 4 and parts[2] == "item":
            pid = parts[3]
            cart = cart_get(db, user_id)
            it = cart.get(pid)
            p = db.products.get(pid)
            if not it or not p:
                await _render(
                    bot=bot, db=db, user_id=user_id, chat_id=chat_id,
                    text="Товару вже немає в кошику.",
                    reply_markup=kb_cart(db, user_id),
                )
                return True

            text = (
                f"🧺 <b>{p.title}</b>\n"
                f"Ціна: {_fmt_price(p.price_uah, p.old_price_uah)}\n"
                f"К-сть: <b>{it.qty}</b>\n"
                f"Сума: <b>{p.price_uah * it.qty} грн</b>"
            )
            photo = p.photos[0] if p.photos else None
            await _render(
                bot=bot, db=db, user_id=user_id, chat_id=chat_id,
                text=text,
                reply_markup=kb_cart_item(pid, it.qty),
                photo=photo,
            )
            return True

        # shop:cart:inc/dec/rm:<pid>
        if len(parts) >= 4 and parts[2] in ("inc", "dec", "rm"):
            sub = parts[2]
            pid = parts[3]
            cart = cart_get(db, user_id)
            it = cart.get(pid)
            if not it:
                await _render(
                    bot=bot, db=db, user_id=user_id, chat_id=chat_id,
                    text="Товару вже немає в кошику.",
                    reply_markup=kb_cart(db, user_id),
                )
                return True

            if sub == "inc":
                it.qty += 1
            elif sub == "dec":
                it.qty -= 1
                if it.qty <= 0:
                    cart.pop(pid, None)
            elif sub == "rm":
                cart.pop(pid, None)

            # показуємо кошик
            total = cart_total_uah(db, user_id)
            await _render(
                bot=bot, db=db, user_id=user_id, chat_id=chat_id,
                text=f"🧺 <b>Кошик</b>\n\nРазом: <b>{total} грн</b>",
                reply_markup=kb_cart(db, user_id),
            )
            return True

    # ---------- CHECKOUT ----------
    if action == "checkout":
        o = make_order_from_cart(db, user_id)
        if not o:
            await _render(
                bot=bot, db=db, user_id=user_id, chat_id=chat_id,
                text="Кошик порожній 🙂",
                reply_markup=kb_home(),
            )
            return True

        await _render(
            bot=bot, db=db, user_id=user_id, chat_id=chat_id,
            text=f"✅ <b>Замовлення створено</b>\nID: <code>{o.id}</code>\nСума: <b>{o.total_uah} грн</b>\n\nМенеджер скоро підтвердить.",
            reply_markup=kb_home(),
        )
        return True

    # ---------- HOT / SALES ----------
    if action == "hot":
        if len(parts) == 2:
            await _render(
                bot=bot, db=db, user_id=user_id, chat_id=chat_id,
                text="🔥 <b>Хіти / Акції</b>\nОбери розділ:",
                reply_markup=kb_hot(),
            )
            return True

        sub = parts[2] if len(parts) >= 3 else ""
        if sub in ("hits", "sales"):
            if sub == "hits":
                prods = [p for p in db.products.values() if p.enabled and p.is_hit]
                title = "🔥 <b>Хіти</b>"
            else:
                prods = [p for p in db.products.values() if p.enabled and p.old_price_uah and p.old_price_uah > p.price_uah]
                title = "🏷 <b>Акції</b>"

            if not prods:
                await _render(
                    bot=bot, db=db, user_id=user_id, chat_id=chat_id,
                    text=title + "\n\nПоки пусто 🙂",
                    reply_markup=kb_hot(),
                )
                return True

            p = prods[0]
            fav = fav_get(db, user_id)
            in_fav = p.id in fav
            text = (
                f"{title}\n\n"
                f"🧾 <b>{p.title}</b>\n"
                f"{_fmt_price(p.price_uah, p.old_price_uah)}\n\n"
                f"{p.desc}"
            )
            photo = p.photos[0] if p.photos else None
            await _render(
                bot=bot, db=db, user_id=user_id, chat_id=chat_id,
                text=text,
                reply_markup=kb_product(p.id, in_fav=in_fav),
                photo=photo,
            )
            return True

    # ---------- SUPPORT ----------
    if action == "support":
        await _render(
            bot=bot, db=db, user_id=user_id, chat_id=chat_id,
            text="📞 <b>Підтримка</b>\n\nТелефон: <b>+38 (___) ___-__-__</b>\nTelegram: @username\n\n(Потім винесемо це в адмінку)",
            reply_markup=kb_back_home(),
        )
        return True

    # ---------- ORDERS ----------
    if action == "orders":
        orders = db.orders.get(int(user_id), [])
        if not orders:
            await _render(
                bot=bot, db=db, user_id=user_id, chat_id=chat_id,
                text="🧾 <b>Історія замовлень</b>\n\nЗамовлень ще немає 🙂",
                reply_markup=kb_back_home(),
            )
            return True

        # покажемо останнє (потім зробимо список)
        o = orders[0]
        lines = [f"🧾 <b>Замовлення</b> <code>{o.id}</code>", f"Статус: <b>{o.status}</b>", f"Сума: <b>{o.total_uah} грн</b>", "", "Товари:"]
        for it in o.items:
            p = db.products.get(it.product_id)
            if not p:
                continue
            lines.append(f"• {p.title} × {it.qty} = {p.price_uah * it.qty} грн")
        await _render(
            bot=bot, db=db, user_id=user_id, chat_id=chat_id,
            text="\n".join(lines),
            reply_markup=kb_back_home(),
        )
        return True

    return True