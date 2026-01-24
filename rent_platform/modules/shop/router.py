from __future__ import annotations

import time
from typing import Any

from aiogram import Bot
from rent_platform.core.tenant_ctx import Tenant
from rent_platform.modules.shop.storage import get_shop_db
from rent_platform.modules.shop.ui import send_or_edit, kb_main, kb_back_menu


def _user_id_from_update(update: dict[str, Any]) -> int | None:
    msg = update.get("message") or {}
    frm = msg.get("from") or {}
    uid = frm.get("id")
    return int(uid) if uid else None


def _get_last_msg_id(db: dict[str, Any], user_id: int) -> int | None:
    ui = db["ui"].get(int(user_id)) or {}
    mid = ui.get("last_message_id")
    return int(mid) if mid else None


def _set_last_msg_id(db: dict[str, Any], user_id: int, message_id: int) -> None:
    db["ui"][int(user_id)] = {"last_message_id": int(message_id)}


def _is_admin(db: dict[str, Any], user_id: int) -> bool:
    return int(user_id) in (db["admin"]["ids"] or set())


async def _show_menu(bot: Bot, chat_id: int, db: dict[str, Any], user_id: int) -> None:
    mid = _get_last_msg_id(db, user_id)
    new_mid = await send_or_edit(
        bot,
        chat_id,
        "🛒 <b>Магазин</b>\n\nОбери розділ нижче 👇",
        message_id=mid,
        kb=kb_main(),
    )
    _set_last_msg_id(db, user_id, new_mid)


async def handle_update(tenant: Tenant, update: dict[str, Any], bot: Bot) -> bool:
    db = get_shop_db(tenant.id)

    message = update.get("message")
    callback = update.get("callback_query")

    # -------------------- MESSAGE --------------------
    if message:
        text = (message.get("text") or "").strip()
        chat_id = (message.get("chat") or {}).get("id")
        if not chat_id:
            return False

        user_id = _user_id_from_update(update) or 0

        # старт/меню
        if text in ("/start", "/shop"):
            await _show_menu(bot, int(chat_id), db, user_id)
            return True

        # -------------------- ADMIN COMMANDS --------------------
        # 1) додати себе в адміни (разово)
        # /shop_admin_add 123456789
        if text.startswith("/shop_admin_add"):
            parts = text.split(maxsplit=1)
            if len(parts) != 2:
                await bot.send_message(chat_id, "Формат: /shop_admin_add <your_user_id>", parse_mode="HTML")
                return True
            try:
                uid = int(parts[1].strip())
            except Exception:
                await bot.send_message(chat_id, "user_id має бути числом.", parse_mode="HTML")
                return True
            db["admin"]["ids"].add(uid)
            await bot.send_message(chat_id, f"✅ Додано адміна: <code>{uid}</code>", parse_mode="HTML")
            return True

        # тільки адмін може далі
        if text.startswith("/shop_") and not _is_admin(db, user_id):
            await bot.send_message(chat_id, "⛔️ Тільки адмін.", parse_mode="HTML")
            return True

        # /shop_cat_add Назва
        if text.startswith("/shop_cat_add"):
            title = text.replace("/shop_cat_add", "", 1).strip()
            if not title:
                await bot.send_message(chat_id, "Формат: /shop_cat_add <назва>", parse_mode="HTML")
                return True
            cid = int(db["seq"]["cat"])
            db["seq"]["cat"] += 1
            db["categories"].append({"id": cid, "title": title[:64]})
            await bot.send_message(chat_id, f"✅ Категорія додана: <b>{title}</b> (id={cid})", parse_mode="HTML")
            return True

        # /shop_prod_add <cat_id>|<title>|<price>|<desc>
        # images поки пусто, потім додамо /shop_prod_img
        if text.startswith("/shop_prod_add"):
            payload = text.replace("/shop_prod_add", "", 1).strip()
            parts = [p.strip() for p in payload.split("|")]
            if len(parts) < 3:
                await bot.send_message(chat_id, "Формат: /shop_prod_add <cat_id>|<title>|<price>|<desc>", parse_mode="HTML")
                return True
            try:
                cat_id = int(parts[0])
                price = int(parts[2])
            except Exception:
                await bot.send_message(chat_id, "cat_id і price мають бути числами.", parse_mode="HTML")
                return True

            title = (parts[1] or "").strip()
            desc = (parts[3] if len(parts) >= 4 else "").strip()

            # перевіримо що категорія існує
            if not any(int(c["id"]) == cat_id for c in db["categories"]):
                await bot.send_message(chat_id, f"Нема такої категорії id={cat_id}", parse_mode="HTML")
                return True

            pid = int(db["seq"]["prod"])
            db["seq"]["prod"] += 1
            db["products"].append({
                "id": pid,
                "category_id": cat_id,
                "title": title[:64] or f"Product {pid}",
                "price_uah": price,
                "desc": desc[:512],
                "images": [],
                "is_hit": False,
                "is_sale": False,
            })
            await bot.send_message(chat_id, f"✅ Товар додано: <b>{title}</b> (id={pid})", parse_mode="HTML")
            return True

        # /shop_help
        if text == "/shop_help":
            await bot.send_message(
                chat_id,
                "🛠 <b>Shop admin</b>\n\n"
                "1) Додай себе в адміни:\n"
                "<code>/shop_admin_add 123456789</code>\n\n"
                "2) Додай категорію:\n"
                "<code>/shop_cat_add Кросівки</code>\n\n"
                "3) Додай товар:\n"
                "<code>/shop_prod_add 1|Nike Air|2500|Опис...</code>\n",
                parse_mode="HTML",
            )
            return True

        return False

    # -------------------- CALLBACK --------------------
    if callback:
        data = (callback.get("data") or "").strip()
        msg = callback.get("message") or {}
        chat_id = (msg.get("chat") or {}).get("id")
        message_id = msg.get("message_id")
        if not chat_id or not message_id:
            return False

        # ack
        try:
            await bot.answer_callback_query(callback_query_id=callback["id"])
        except Exception:
            pass

        # у callback_query user_id тут:
        cb_from = callback.get("from") or {}
        user_id = int(cb_from.get("id") or 0)

        if data == "shop:menu":
            new_mid = await send_or_edit(
                bot,
                int(chat_id),
                "🛒 <b>Магазин</b>\n\nОбери розділ нижче 👇",
                message_id=int(message_id),
                kb=kb_main(),
            )
            _set_last_msg_id(db, user_id, new_mid)
            return True

        if data == "shop:catalog":
            text = "🛍 <b>Каталог</b>\n\n"
            if not db["categories"]:
                text += "Поки що немає категорій.\n\n(Адмін: /shop_cat_add ...)"
            else:
                text += "Категорії додані ✅\n\n(Наступний крок — показ списку категорій кнопками)"
            await send_or_edit(bot, int(chat_id), text, message_id=int(message_id), kb=kb_back_menu())
            _set_last_msg_id(db, user_id, int(message_id))
            return True

        if data == "shop:cart":
            await send_or_edit(
                bot,
                int(chat_id),
                "🛒 <b>Кошик</b>\n\nПоки порожньо.\n\n(Наступний крок — qty ➖ ➕ 🗑 + сума)",
                message_id=int(message_id),
                kb=kb_back_menu(),
            )
            _set_last_msg_id(db, user_id, int(message_id))
            return True

        if data == "shop:fav":
            await send_or_edit(
                bot,
                int(chat_id),
                "⭐️ <b>Обране</b>\n\nПоки порожньо.\n\n(Наступний крок — додавання з картки товару)",
                message_id=int(message_id),
                kb=kb_back_menu(),
            )
            _set_last_msg_id(db, user_id, int(message_id))
            return True

        if data == "shop:hits":
            await send_or_edit(
                bot,
                int(chat_id),
                "🔥 <b>Хіти / Акції</b>\n\nПоки немає.\n\n(Адмін потім ставитиме is_hit/is_sale)",
                message_id=int(message_id),
                kb=kb_back_menu(),
            )
            _set_last_msg_id(db, user_id, int(message_id))
            return True

        if data == "shop:support":
            st = db["settings"]["support_text"]
            await send_or_edit(
                bot,
                int(chat_id),
                f"🆘 <b>Підтримка</b>\n\n{st}",
                message_id=int(message_id),
                kb=kb_back_menu(),
            )
            _set_last_msg_id(db, user_id, int(message_id))
            return True

        if data == "shop:orders":
            await send_or_edit(
                bot,
                int(chat_id),
                "📜 <b>Історія замовлень</b>\n\nПоки замовлень немає.",
                message_id=int(message_id),
                kb=kb_back_menu(),
            )
            _set_last_msg_id(db, user_id, int(message_id))
            return True

        return False

    return False