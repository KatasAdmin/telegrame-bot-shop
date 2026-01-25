from __future__ import annotations

from typing import Any

from aiogram import Bot

from rent_platform.modules.telegram_shop.repo.products import ProductsRepo

# Простий in-memory state (потім замінимо на БД/redis)
# key: (tenant_id, chat_id) -> {"mode": "...", "product_id": int}
_PENDING: dict[tuple[str, int], dict[str, Any]] = {}


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
        return int(s)
    except Exception:
        return None


def _extract_message(data: dict[str, Any]) -> dict | None:
    return data.get("message") or data.get("edited_message")


def _extract_callback(data: dict[str, Any]) -> dict | None:
    return data.get("callback_query")


def _admin_menu_kb() -> dict:
    # Inline keyboard as raw dict (aiogram Bot API accepts it)
    return {
        "inline_keyboard": [
            [
                {"text": "➕ Додати товар", "callback_data": "tgadm:add"},
                {"text": "📦 Товари", "callback_data": "tgadm:list"},
            ],
            [
                {"text": "📝 Опис товару", "callback_data": "tgadm:desc"},
                {"text": "📷 Фото товару", "callback_data": "tgadm:photo"},
            ],
            [
                {"text": "⛔ Вимкнути", "callback_data": "tgadm:disable"},
                {"text": "✅ Увімкнути", "callback_data": "tgadm:enable"},
            ],
            [
                {"text": "❌ Скинути дію", "callback_data": "tgadm:cancel"},
            ],
        ]
    }


async def _send_admin_menu(bot: Bot, chat_id: int) -> None:
    await bot.send_message(
        chat_id,
        "🛠 *Адмінка магазину*\n\n"
        "Все робимо кнопками. Обери дію 👇",
        parse_mode="Markdown",
        reply_markup=_admin_menu_kb(),
    )


async def _send_products_list(bot: Bot, chat_id: int, tenant_id: str) -> None:
    items = await ProductsRepo.list_active(tenant_id, limit=50)
    if not items:
        await bot.send_message(chat_id, "Поки що немає активних товарів.")
        return

    lines = ["📦 *Активні товари:*"]
    for p in items:
        lines.append(f"{int(p['id'])}) {p['name']} — {_fmt_money(int(p.get('price_kop') or 0))}")
    await bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")


async def _set_pending(tenant_id: str, chat_id: int, mode: str, product_id: int = 0) -> None:
    _PENDING[(tenant_id, chat_id)] = {"mode": mode, "product_id": int(product_id)}


def _pop_pending(tenant_id: str, chat_id: int) -> dict[str, Any] | None:
    return _PENDING.pop((tenant_id, chat_id), None)


def _get_pending(tenant_id: str, chat_id: int) -> dict[str, Any] | None:
    return _PENDING.get((tenant_id, chat_id))


async def handle_update(*, tenant: dict, data: dict[str, Any], bot: Bot) -> bool:
    tenant_id = str(tenant["id"])

    # ---------- callbacks (inline admin menu) ----------
    cb = _extract_callback(data)
    if cb:
        payload = (cb.get("data") or "").strip()
        if not payload.startswith("tgadm:"):
            return False

        chat_id = int(cb["message"]["chat"]["id"])
        cb_id = cb.get("id")
        action = payload.split(":", 1)[1]

        if cb_id:
            await bot.answer_callback_query(cb_id)

        if action == "cancel":
            _pop_pending(tenant_id, chat_id)
            await bot.send_message(chat_id, "✅ Ок, скинув дію. Обери нову 👇", reply_markup=_admin_menu_kb())
            return True

        if action == "list":
            await _send_products_list(bot, chat_id, tenant_id)
            return True

        if action == "add":
            await _set_pending(tenant_id, chat_id, "add")
            await bot.send_message(
                chat_id,
                "➕ Додавання товару\n\n"
                "Надішли одним повідомленням:\n"
                "`Назва | 150.00`\n"
                "або `Назва | 15000` (в коп.)",
                parse_mode="Markdown",
            )
            return True

        if action == "desc":
            await _set_pending(tenant_id, chat_id, "desc")
            await bot.send_message(
                chat_id,
                "📝 Опис товару\n\n"
                "Надішли:\n"
                "`<id> | текст опису...`",
                parse_mode="Markdown",
            )
            return True

        if action == "photo":
            await _set_pending(tenant_id, chat_id, "photo_wait_id")
            await bot.send_message(
                chat_id,
                "📷 Фото товару\n\n"
                "Надішли ID товару цифрою (наприклад `12`).\n"
                "Потім я попрошу надіслати фото.",
                parse_mode="Markdown",
            )
            return True

        if action in ("disable", "enable"):
            await _set_pending(tenant_id, chat_id, action)
            await bot.send_message(
                chat_id,
                ("⛔ Вимкнути" if action == "disable" else "✅ Увімкнути")
                + " товар\n\nНадішли ID товару цифрою (наприклад `12`).",
                parse_mode="Markdown",
            )
            return True

        return False

    # ---------- messages ----------
    msg = _extract_message(data)
    if not msg:
        return False

    chat_id = int(msg["chat"]["id"])
    text = (msg.get("text") or "").strip()

    # вход в адмінку
    if text in ("/a", "/a_help"):
        await _send_admin_menu(bot, chat_id)
        return True

    pending = _get_pending(tenant_id, chat_id)

    # --- якщо чекаємо ФОТО ---
    if pending and pending.get("mode") == "photo_wait_photo":
        photos = msg.get("photo") or []
        if not photos:
            await bot.send_message(chat_id, "Надішли саме фото (не файл).")
            return True

        product_id = int(pending.get("product_id") or 0)
        if product_id <= 0:
            _pop_pending(tenant_id, chat_id)
            await bot.send_message(chat_id, "❌ Нема product_id в стані. Спробуй ще раз.", reply_markup=_admin_menu_kb())
            return True

        file_id = str(photos[-1]["file_id"])
        await ProductsRepo.add_product_photo(tenant_id, product_id, file_id)
        _pop_pending(tenant_id, chat_id)
        await bot.send_message(chat_id, f"✅ Фото додано до товару #{product_id}", reply_markup=_admin_menu_kb())
        return True

    # --- якщо немає pending — нічого не робимо (адмінка тільки коли вибрав дію) ---
    if not pending:
        return False

    mode = str(pending.get("mode") or "")

    # --- add product ---
    if mode == "add":
        if "|" not in text:
            await bot.send_message(chat_id, "Формат: `Назва | 150.00`", parse_mode="Markdown")
            return True
        name_part, price_part = [x.strip() for x in text.split("|", 1)]
        name = (name_part or "").strip()
        if not name:
            await bot.send_message(chat_id, "Назва не може бути пустою.")
            return True
        price_kop = _parse_price_to_kop(price_part)
        if price_kop is None:
            await bot.send_message(chat_id, "Ціна не розпізнана. Приклад: 150.00 або 15000")
            return True

        pid = await ProductsRepo.add(tenant_id, name, int(price_kop), is_active=True)
        _pop_pending(tenant_id, chat_id)
        if not pid:
            await bot.send_message(chat_id, "❌ Не вдалося додати товар (перевір БД/міграції).", reply_markup=_admin_menu_kb())
            return True

        await bot.send_message(chat_id, f"✅ Додано: {pid}) {name} — {_fmt_money(price_kop)}", reply_markup=_admin_menu_kb())
        return True

    # --- set desc ---
    if mode == "desc":
        if "|" not in text:
            await bot.send_message(chat_id, "Формат: `<id> | текст опису...`", parse_mode="Markdown")
            return True
        id_part, desc_part = [x.strip() for x in text.split("|", 1)]
        if not id_part.isdigit():
            await bot.send_message(chat_id, "ID має бути цифрою.")
            return True
        pid = int(id_part)
        await ProductsRepo.set_description(tenant_id, pid, desc_part)
        _pop_pending(tenant_id, chat_id)
        await bot.send_message(chat_id, f"✅ Опис збережено для #{pid}", reply_markup=_admin_menu_kb())
        return True

    # --- photo: step 1 (wait id) ---
    if mode == "photo_wait_id":
        if not text.isdigit():
            await bot.send_message(chat_id, "Надішли тільки цифру ID товару (наприклад 12).")
            return True
        pid = int(text)
        await _set_pending(tenant_id, chat_id, "photo_wait_photo", pid)
        await bot.send_message(chat_id, f"📷 Ок, тепер надішли фото для товару #{pid}.")
        return True

    # --- enable/disable ---
    if mode in ("disable", "enable"):
        if not text.isdigit():
            await bot.send_message(chat_id, "Надішли тільки цифру ID товару.")
            return True
        pid = int(text)
        is_active = mode == "enable"
        await ProductsRepo.set_active(tenant_id, pid, is_active)
        _pop_pending(tenant_id, chat_id)
        await bot.send_message(chat_id, f"✅ Товар {pid} {'увімкнено' if is_active else 'вимкнено'}.", reply_markup=_admin_menu_kb())
        return True

    return False