from __future__ import annotations

from typing import Any

from aiogram import Bot

from rent_platform.modules.telegram_shop.repo.products import ProductsRepo

# -----------------------------
# In-memory wizard state
# key: (tenant_id, chat_id) -> state dict
# -----------------------------
_STATE: dict[tuple[str, int], dict[str, Any]] = {}


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

        # якщо адмін ввів 1500 -> трактуємо як грн (щоб було зручно)
        # але якщо хочеш навпаки (в коп.) — скажеш, поміняємо.
        val = int(s)
        if val < 100000:  # до 1000 грн умовно
            return val * 100
        return val
    except Exception:
        return None


def _extract_message(data: dict[str, Any]) -> dict | None:
    return data.get("message") or data.get("edited_message")


def _extract_callback(data: dict[str, Any]) -> dict | None:
    return data.get("callback_query")


def _kb(rows: list[list[tuple[str, str]]]) -> dict:
    """
    rows: [[(text, callback_data), ...], ...]
    """
    return {
        "inline_keyboard": [
            [{"text": t, "callback_data": d} for (t, d) in row]
            for row in rows
        ]
    }


def _admin_home_kb() -> dict:
    return _kb([
        [("➕ Додати товар", "tgadm:wiz_start"), ("📦 Товари", "tgadm:list")],
        [("⛔ Вимкнути товар", "tgadm:disable"), ("✅ Увімкнути товар", "tgadm:enable")],
        [("❌ Скинути дію", "tgadm:cancel")],
    ])


def _wiz_nav_kb(*, allow_skip: bool = False) -> dict:
    row: list[tuple[str, str]] = [("❌ Скасувати", "tgadm:cancel")]
    if allow_skip:
        row.insert(0, ("⏭ Пропустити", "tgadm:wiz_skip"))
    return _kb([row])


def _wiz_photos_kb(*, product_id: int) -> dict:
    # саме те, що ти просив: після фото -> "додати ще" або "готово"
    return _kb([
        [("📷 Додати ще фото", "tgadm:wiz_photo_more"), ("✅ Готово", "tgadm:wiz_done")],
        [("📝 Додати/змінити опис", f"tgadm:wiz_desc_edit:{product_id}")],
        [("❌ Скасувати", "tgadm:cancel")],
    ])


def _wiz_finish_kb(*, product_id: int) -> dict:
    return _kb([
        [("📷 Додати фото", f"tgadm:wiz_photo_more:{product_id}"), ("📝 Опис", f"tgadm:wiz_desc_edit:{product_id}")],
        [("➕ Додати ще товар", "tgadm:wiz_start"), ("📦 Товари", "tgadm:list")],
        [("🏠 В адмін-меню", "tgadm:home")],
    ])


def _state_get(tenant_id: str, chat_id: int) -> dict[str, Any] | None:
    return _STATE.get((tenant_id, chat_id))


def _state_set(tenant_id: str, chat_id: int, st: dict[str, Any]) -> None:
    _STATE[(tenant_id, chat_id)] = st


def _state_clear(tenant_id: str, chat_id: int) -> None:
    _STATE.pop((tenant_id, chat_id), None)


async def _send_admin_home(bot: Bot, chat_id: int) -> None:
    await bot.send_message(
        chat_id,
        "🛠 *Адмінка магазину*\n\n"
        "Тут все через wizard і кнопки 👇",
        parse_mode="Markdown",
        reply_markup=_admin_home_kb(),
    )


async def _send_products_list(bot: Bot, chat_id: int, tenant_id: str) -> None:
    items = await ProductsRepo.list_active(tenant_id, limit=100)
    if not items:
        await bot.send_message(chat_id, "Поки що немає активних товарів.")
        return

    lines = ["📦 *Активні товари:*"]
    for p in items:
        lines.append(f"{int(p['id'])}) {p['name']} — {_fmt_money(int(p.get('price_kop') or 0))}")
    await bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")


async def _wiz_ask_name(bot: Bot, chat_id: int, tenant_id: str) -> None:
    _state_set(tenant_id, chat_id, {"mode": "wiz_name", "draft": {}})
    await bot.send_message(
        chat_id,
        "➕ *Новий товар*\n\n"
        "1/4 Введи *назву* товару:",
        parse_mode="Markdown",
        reply_markup=_wiz_nav_kb(),
    )


async def _wiz_ask_price(bot: Bot, chat_id: int, tenant_id: str, draft: dict) -> None:
    _state_set(tenant_id, chat_id, {"mode": "wiz_price", "draft": draft})
    await bot.send_message(
        chat_id,
        "2/4 Введи *ціну* (наприклад `1200.50` або `1200`):",
        parse_mode="Markdown",
        reply_markup=_wiz_nav_kb(),
    )


async def _wiz_ask_desc(bot: Bot, chat_id: int, tenant_id: str, draft: dict) -> None:
    _state_set(tenant_id, chat_id, {"mode": "wiz_desc", "draft": draft})
    await bot.send_message(
        chat_id,
        "3/4 Додай *опис* (або натисни `Пропустити`):",
        parse_mode="Markdown",
        reply_markup=_wiz_nav_kb(allow_skip=True),
    )


async def _wiz_ask_category_stub(bot: Bot, chat_id: int, tenant_id: str, draft: dict) -> None:
    # Гачок під категорії. Поки просто пропускаємо.
    _state_set(tenant_id, chat_id, {"mode": "wiz_category_stub", "draft": draft})
    await bot.send_message(
        chat_id,
        "4/4 *Категорія*\n\n"
        "Скоро додамо категорії. Поки натисни `Пропустити` 👇",
        parse_mode="Markdown",
        reply_markup=_wiz_nav_kb(allow_skip=True),
    )


async def _wiz_create_product(bot: Bot, chat_id: int, tenant_id: str, draft: dict) -> int | None:
    name = str(draft.get("name") or "").strip()
    price_kop = int(draft.get("price_kop") or 0)
    desc = str(draft.get("description") or "").strip()

    pid = await ProductsRepo.add(tenant_id, name, price_kop, is_active=True)
    if not pid:
        return None

    if desc:
        await ProductsRepo.set_description(tenant_id, pid, desc)

    return int(pid)


async def _wiz_photos_start(bot: Bot, chat_id: int, tenant_id: str, product_id: int) -> None:
    _state_set(tenant_id, chat_id, {"mode": "wiz_photo", "product_id": int(product_id)})
    await bot.send_message(
        chat_id,
        f"📷 Фото для товару *#{product_id}*\n\n"
        "Надсилай фото (можна кілька). Після кожного фото я спитаю — додати ще чи Готово.",
        parse_mode="Markdown",
        reply_markup=_wiz_photos_kb(product_id=product_id),
    )


async def _wiz_finish(bot: Bot, chat_id: int, product_id: int) -> None:
    await bot.send_message(
        chat_id,
        f"✅ *Готово!* Товар *#{product_id}* створено.\n\n"
        "Можеш додати фото/опис або створити ще.",
        parse_mode="Markdown",
        reply_markup=_wiz_finish_kb(product_id=product_id),
    )


def _extract_image_file_id(msg: dict) -> str | None:
    """
    Telegram може прислати картинку як:
    - message.photo (звичайне фото)
    - message.document (як файл), з mime_type image/*
    """
    photos = msg.get("photo") or []
    if photos:
        fid = photos[-1].get("file_id")
        return str(fid) if fid else None

    doc = msg.get("document") or {}
    mime = (doc.get("mime_type") or "").lower()
    if mime.startswith("image/"):
        fid = doc.get("file_id")
        return str(fid) if fid else None

    return None


async def handle_update(*, tenant: dict, data: dict[str, Any], bot: Bot) -> bool:
    tenant_id = str(tenant["id"])

    # ---------- callbacks ----------
    cb = _extract_callback(data)
    if cb:
        payload = (cb.get("data") or "").strip()
        if not payload.startswith("tgadm:"):
            return False

        chat_id = int(cb["message"]["chat"]["id"])
        cb_id = cb.get("id")
        if cb_id:
            await bot.answer_callback_query(cb_id)

        parts = payload.split(":")
        action = parts[1] if len(parts) > 1 else ""
        pid = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0

        if action == "home":
            _state_clear(tenant_id, chat_id)
            await _send_admin_home(bot, chat_id)
            return True

        if action == "cancel":
            _state_clear(tenant_id, chat_id)
            await bot.send_message(chat_id, "✅ Скасовано.", reply_markup=_admin_home_kb())
            return True

        if action == "list":
            _state_clear(tenant_id, chat_id)
            await _send_products_list(bot, chat_id, tenant_id)
            return True

        if action == "disable":
            _state_set(tenant_id, chat_id, {"mode": "disable"})
            await bot.send_message(chat_id, "Надішли ID товару (цифрою), який вимкнути:", reply_markup=_wiz_nav_kb())
            return True

        if action == "enable":
            _state_set(tenant_id, chat_id, {"mode": "enable"})
            await bot.send_message(chat_id, "Надішли ID товару (цифрою), який увімкнути:", reply_markup=_wiz_nav_kb())
            return True

        if action == "wiz_start":
            await _wiz_ask_name(bot, chat_id, tenant_id)
            return True

        if action == "wiz_skip":
            st = _state_get(tenant_id, chat_id) or {}
            mode = st.get("mode")
            draft = st.get("draft") or {}

            if mode == "wiz_desc":
                draft["description"] = ""
                await _wiz_ask_category_stub(bot, chat_id, tenant_id, draft)
                return True

            if mode == "wiz_category_stub":
                pid2 = await _wiz_create_product(bot, chat_id, tenant_id, draft)
                _state_clear(tenant_id, chat_id)
                if not pid2:
                    await bot.send_message(
                        chat_id,
                        "❌ Не вдалося створити товар (перевір БД/міграції).",
                        reply_markup=_admin_home_kb(),
                    )
                    return True

                await _wiz_photos_start(bot, chat_id, tenant_id, pid2)
                return True

            return True

        if action == "wiz_done":
            st = _state_get(tenant_id, chat_id) or {}
            product_id = int(st.get("product_id") or 0)
            _state_clear(tenant_id, chat_id)
            if product_id > 0:
                await _wiz_finish(bot, chat_id, product_id)
                return True
            await bot.send_message(chat_id, "✅ Готово.", reply_markup=_admin_home_kb())
            return True

        if action == "wiz_photo_more":
            st = _state_get(tenant_id, chat_id) or {}
            product_id = pid or int(st.get("product_id") or 0)
            if product_id <= 0:
                await bot.send_message(chat_id, "❌ Нема product_id. Відкрий wizard заново.", reply_markup=_admin_home_kb())
                return True
            await _wiz_photos_start(bot, chat_id, tenant_id, product_id)
            return True

        if action == "wiz_desc_edit":
            if pid <= 0:
                await bot.send_message(chat_id, "❌ Нема ID товару.", reply_markup=_admin_home_kb())
                return True
            _state_set(tenant_id, chat_id, {"mode": "desc_edit", "product_id": int(pid)})
            await bot.send_message(
                chat_id,
                f"📝 Надішли новий опис для товару #{pid} (або `Пропустити`, щоб очистити):",
                parse_mode="Markdown",
                reply_markup=_wiz_nav_kb(allow_skip=True),
            )
            return True

        return False

    # ---------- messages ----------
    msg = _extract_message(data)
    if not msg:
        return False

    chat_id = int(msg["chat"]["id"])
    text = (msg.get("text") or "").strip()

    # вход
    if text in ("/a", "/a_help"):
        await _send_admin_home(bot, chat_id)
        return True

    st = _state_get(tenant_id, chat_id)
    if not st:
        return False

    mode = str(st.get("mode") or "")

    # ---- фото у wizard ----
    if mode == "wiz_photo":
        product_id = int(st.get("product_id") or 0)
        if product_id <= 0:
            _state_clear(tenant_id, chat_id)
            await bot.send_message(chat_id, "❌ Нема product_id в стані.", reply_markup=_admin_home_kb())
            return True

        file_id = _extract_image_file_id(msg)
        if not file_id:
            await bot.send_message(
                chat_id,
                "Надішли *фото* (саме фото або картинку-файл). Або натисни `Готово`.",
                parse_mode="Markdown",
                reply_markup=_wiz_photos_kb(product_id=product_id),
            )
            return True

        await ProductsRepo.add_product_photo(tenant_id, product_id, file_id)

        await bot.send_message(
            chat_id,
            f"✅ Фото додано до *#{product_id}*.\n\nХочеш додати ще?",
            parse_mode="Markdown",
            reply_markup=_wiz_photos_kb(product_id=product_id),
        )
        return True

    # ---- enable/disable ----
    if mode in ("enable", "disable"):
        if not text.isdigit():
            await bot.send_message(chat_id, "Надішли тільки цифру ID.")
            return True
        pid = int(text)
        await ProductsRepo.set_active(tenant_id, pid, mode == "enable")
        _state_clear(tenant_id, chat_id)
        await bot.send_message(chat_id, f"✅ Товар {pid} {'увімкнено' if mode=='enable' else 'вимкнено'}.", reply_markup=_admin_home_kb())
        return True

    # ---- wizard steps ----
    if mode == "wiz_name":
        name = (text or "").strip()
        if not name:
            await bot.send_message(chat_id, "Назва не може бути пустою.")
            return True
        draft = st.get("draft") or {}
        draft["name"] = name[:128]
        await _wiz_ask_price(bot, chat_id, tenant_id, draft)
        return True

    if mode == "wiz_price":
        price_kop = _parse_price_to_kop(text)
        if price_kop is None or price_kop <= 0:
            await bot.send_message(chat_id, "Ціна не розпізнана. Приклад: `1200.50` або `1200`", parse_mode="Markdown")
            return True
        draft = st.get("draft") or {}
        draft["price_kop"] = int(price_kop)
        await _wiz_ask_desc(bot, chat_id, tenant_id, draft)
        return True

    if mode == "wiz_desc":
        draft = st.get("draft") or {}
        draft["description"] = (text or "").strip()
        await _wiz_ask_category_stub(bot, chat_id, tenant_id, draft)
        return True

    if mode == "wiz_category_stub":
        draft = st.get("draft") or {}
        pid2 = await _wiz_create_product(bot, chat_id, tenant_id, draft)
        _state_clear(tenant_id, chat_id)
        if not pid2:
            await bot.send_message(chat_id, "❌ Не вдалося створити товар (перевір БД/міграції).", reply_markup=_admin_home_kb())
            return True
        await _wiz_photos_start(bot, chat_id, tenant_id, pid2)
        return True

    # ---- quick desc edit ----
    if mode == "desc_edit":
        product_id = int(st.get("product_id") or 0)
        if product_id <= 0:
            _state_clear(tenant_id, chat_id)
            await bot.send_message(chat_id, "❌ Нема ID товару.", reply_markup=_admin_home_kb())
            return True

        # якщо натиснув "Пропустити" — очищаємо опис
        if text == "" or text.lower() == "пропустити":
            await ProductsRepo.set_description(tenant_id, product_id, "")
            _state_clear(tenant_id, chat_id)
            await bot.send_message(chat_id, f"✅ Опис очищено для #{product_id}.", reply_markup=_admin_home_kb())
            return True

        await ProductsRepo.set_description(tenant_id, product_id, text)
        _state_clear(tenant_id, chat_id)
        await bot.send_message(chat_id, f"✅ Опис оновлено для #{product_id}.", reply_markup=_admin_home_kb())
        return True

    return False