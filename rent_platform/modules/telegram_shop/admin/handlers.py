from __future__ import annotations

from typing import Any

from aiogram import Bot

from rent_platform.modules.telegram_shop.repo.products import ProductsRepo


def _fmt_money(kop: int) -> str:
    kop = int(kop or 0)
    грн = kop // 100
    коп = kop % 100
    return f"{грн}.{коп:02d} грн"


def _parse_price_to_kop(raw: str) -> int | None:
    s = (raw or "").replace("грн", "").replace(" ", "").replace(",", ".").strip()
    if not s:
        return None
    try:
        if "." in s:
            грн_s, коп_s = (s.split(".", 1) + ["0"])[:2]
            грн = int(грн_s) if грн_s else 0
            коп = int((коп_s + "0")[:2])
            return грн * 100 + коп
        return int(s)  # treat as kop
    except Exception:
        return None


# pending photo upload state (tenant_id:user_id -> product_id)
_PENDING_PHOTO: dict[str, int] = {}


def _pending_key(tenant_id: str, user_id: int) -> str:
    return f"{tenant_id}:{int(user_id)}"


async def handle_update(*, tenant: dict, data: dict[str, Any], bot: Bot) -> bool:
    """
    Admin-only update handler.
    Return True if handled.
    """
    msg = data.get("message") or data.get("edited_message")
    if not msg:
        return False

    chat_id = int(msg["chat"]["id"])
    user_id = int(msg["from"]["id"])
    tenant_id = str(tenant["id"])

    text = (msg.get("text") or "").strip()

    # 0) PHOTO MODE: if admin previously started /a_photo <id>, accept incoming photo messages
    if not text:
        # check photo payload
        photos = msg.get("photo") or []
        if photos:
            key = _pending_key(tenant_id, user_id)
            pid = _PENDING_PHOTO.get(key)
            if not pid:
                return False  # no pending mode

            # choose best resolution
            file_id = str(photos[-1].get("file_id") or "").strip()
            if not file_id:
                await bot.send_message(chat_id, "Не бачу file_id у фото 😅")
                return True

            photo_db_id = await ProductsRepo.add_product_photo(tenant_id, pid, file_id)
            if not photo_db_id:
                await bot.send_message(chat_id, "Не вдалося зберегти фото (перевір таблицю/міграцію).")
                return True

            await bot.send_message(
                chat_id,
                f"📸 Фото додано до товару #{pid}. (ще можна надсилати фото)\n"
                f"Завершити: /a_photo_done",
            )
            return True

        return False

    # /a_help
    if text == "/a_help":
        await bot.send_message(
            chat_id,
            "🛠 Адмін-команди:\n\n"
            "➕ Додати товар:\n"
            "/a_add_product Назва | 150.00\n"
            "або /a_add_product Назва | 15000  (в коп.)\n\n"
            "📦 Список активних:\n"
            "/a_list_products\n\n"
            "📝 Опис:\n"
            "/a_desc 12 Текст опису...\n\n"
            "📸 Фото:\n"
            "/a_photo 12   (потім надішли фото 1..N)\n"
            "/a_photo_done (завершити режим)\n"
            "/a_photos 12  (список/кількість)\n\n"
            "🔌 Вимк/увімк:\n"
            "/a_disable 12\n"
            "/a_enable 12\n",
        )
        return True

    # /a_add_product Name | 150.00
    if text.startswith("/a_add_product"):
        payload = text[len("/a_add_product"):].strip()
        if "|" not in payload:
            await bot.send_message(chat_id, "Формат: /a_add_product Назва | 150.00")
            return True

        name_part, price_part = [x.strip() for x in payload.split("|", 1)]
        name = (name_part or "").strip()
        if not name:
            await bot.send_message(chat_id, "Назва не може бути пустою.")
            return True

        price_kop = _parse_price_to_kop(price_part)
        if price_kop is None:
            await bot.send_message(chat_id, "Ціна не розпізнана. Приклад: 150.00 або 15000")
            return True

        pid = await ProductsRepo.add(tenant_id, name, int(price_kop), is_active=True)
        if not pid:
            await bot.send_message(chat_id, "Не вдалося додати товар (перевір БД/міграції).")
            return True

        await bot.send_message(chat_id, f"✅ Додано: {pid}) {name} — {_fmt_money(price_kop)}")
        return True

    # /a_list_products
    if text == "/a_list_products":
        items = await ProductsRepo.list_active(tenant_id, limit=50)
        if not items:
            await bot.send_message(chat_id, "Поки що немає активних товарів.")
            return True

        lines = ["📦 Активні товари:"]
        for p in items:
            lines.append(f"{int(p['id'])}) {p['name']} — {_fmt_money(int(p.get('price_kop') or 0))}")
        await bot.send_message(chat_id, "\n".join(lines))
        return True

    # /a_disable 12  /a_enable 12
    if text.startswith("/a_disable ") or text.startswith("/a_enable "):
        parts = text.split()
        if len(parts) != 2 or not parts[1].isdigit():
            await bot.send_message(chat_id, "Формат: /a_disable 12 або /a_enable 12")
            return True
        pid = int(parts[1])
        is_active = text.startswith("/a_enable ")
        await ProductsRepo.set_active(tenant_id, pid, is_active)
        await bot.send_message(chat_id, f"✅ Товар {pid} {'увімкнено' if is_active else 'вимкнено'}.")
        return True

    # /a_desc 12 some text...
    if text.startswith("/a_desc "):
        # формат: /a_desc <id> <text...>
        parts = text.split(maxsplit=2)
        if len(parts) < 3 or not parts[1].isdigit():
            await bot.send_message(chat_id, "Формат: /a_desc 12 Текст опису...")
            return True
        pid = int(parts[1])
        desc = parts[2].strip()
        await ProductsRepo.set_description(tenant_id, pid, desc)
        await bot.send_message(chat_id, f"✅ Опис збережено для товару #{pid}.")
        return True

    # /a_photo 12 -> enable photo mode
    if text.startswith("/a_photo "):
        parts = text.split()
        if len(parts) != 2 or not parts[1].isdigit():
            await bot.send_message(chat_id, "Формат: /a_photo 12")
            return True
        pid = int(parts[1])
        _PENDING_PHOTO[_pending_key(tenant_id, user_id)] = pid
        await bot.send_message(
            chat_id,
            f"📸 Режим фото для товару #{pid} увімкнено.\n"
            f"Надішли фото (можна кілька підряд).\n"
            f"Завершити: /a_photo_done",
        )
        return True

    # /a_photo_done -> disable photo mode
    if text == "/a_photo_done":
        key = _pending_key(tenant_id, user_id)
        if key in _PENDING_PHOTO:
            pid = _PENDING_PHOTO.pop(key)
            await bot.send_message(chat_id, f"✅ Режим фото завершено для товару #{pid}.")
        else:
            await bot.send_message(chat_id, "Режим фото не активний.")
        return True

    # /a_photos 12 -> list photos
    if text.startswith("/a_photos "):
        parts = text.split()
        if len(parts) != 2 or not parts[1].isdigit():
            await bot.send_message(chat_id, "Формат: /a_photos 12")
            return True
        pid = int(parts[1])
        photos = await ProductsRepo.list_product_photos(tenant_id, pid, limit=10)
        cover = await ProductsRepo.get_cover_photo_file_id(tenant_id, pid)

        if not photos:
            await bot.send_message(chat_id, f"Фото для товару #{pid}: поки що немає.\nДодати: /a_photo {pid}")
            return True

        lines = [f"📸 Фото товару #{pid}: {len(photos)} шт (показую до 10)"]
        if cover:
            lines.append("🖼 Cover: є")
        for ph in photos:
            lines.append(f"• id={ph['id']} sort={ph['sort']}")
        await bot.send_message(chat_id, "\n".join(lines))
        return True

    return False