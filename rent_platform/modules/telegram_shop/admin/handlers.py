from __future__ import annotations

from typing import Any

from aiogram import Bot

from rent_platform.modules.telegram_shop.repo.products import ProductsRepo

# CategoriesRepo optional-import (so admin doesn't crash if you haven't added file yet)
try:
    from rent_platform.modules.telegram_shop.repo.categories import CategoriesRepo  # type: ignore
except Exception:  # pragma: no cover
    CategoriesRepo = None  # type: ignore


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
        val = int(s)
        if val < 100000:
            return val * 100
        return val
    except Exception:
        return None


def _extract_message(data: dict[str, Any]) -> dict | None:
    return data.get("message") or data.get("edited_message")


def _extract_callback(data: dict[str, Any]) -> dict | None:
    return data.get("callback_query")


def _kb(rows: list[list[tuple[str, str]]]) -> dict:
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for (t, d) in row] for row in rows]}


# -----------------------------
# Меню: "в одному місці" -> 📦 Каталог
# -----------------------------
def _admin_home_kb() -> dict:
    return _kb([
        [("📦 Каталог", "tgadm:catalog")],
        [("❌ Скинути дію", "tgadm:cancel")],
    ])


def _catalog_kb() -> dict:
    return _kb([
        [("📁 Категорії", "tgadm:cat_menu"), ("📦 Товари", "tgadm:prod_menu")],
        [("🗃 Архів (вимкнені)", "tgadm:archive"), ("🔥 Акції / Знижки", "tgadm:promos")],
        [("🏠 В адмін-меню", "tgadm:home")],
    ])


def _products_menu_kb() -> dict:
    return _kb([
        [("➕ Додати товар", "tgadm:wiz_start"), ("📦 Список активних", "tgadm:list")],
        [("⛔ Вимкнути товар", "tgadm:disable"), ("✅ Увімкнути товар", "tgadm:enable")],
        [("⬅️ Назад", "tgadm:catalog")],
    ])


def _categories_menu_kb() -> dict:
    return _kb([
        [("➕ Створити категорію", "tgadm:cat_create"), ("📋 Список категорій", "tgadm:cat_list")],
        [("⬅️ Назад", "tgadm:catalog")],
    ])


def _wiz_nav_kb(*, allow_skip: bool = False) -> dict:
    row: list[tuple[str, str]] = [("❌ Скасувати", "tgadm:cancel")]
    if allow_skip:
        row.insert(0, ("⏭ Пропустити", "tgadm:wiz_skip"))
    return _kb([row])


def _wiz_photos_kb(*, product_id: int) -> dict:
    return _kb([
        [("📷 Додати ще фото", "tgadm:wiz_photo_more"), ("✅ Готово", "tgadm:wiz_done")],
        [("📝 Додати/змінити опис", f"tgadm:wiz_desc_edit:{product_id}")],
        [("❌ Скасувати", "tgadm:cancel")],
    ])


def _wiz_finish_kb(*, product_id: int) -> dict:
    return _kb([
        [("📷 Додати фото", f"tgadm:wiz_photo_more:{product_id}"), ("📝 Опис", f"tgadm:wiz_desc_edit:{product_id}")],
        [("➕ Додати ще товар", "tgadm:wiz_start"), ("📦 Товари", "tgadm:prod_menu")],
        [("📦 Каталог", "tgadm:catalog")],
    ])


def _category_pick_kb(categories: list[dict], *, default_category_id: int | None) -> dict:
    rows: list[list[tuple[str, str]]] = []
    for c in categories:
        cid = int(c["id"])
        name = str(c["name"])
        badge = "✅ " if default_category_id and cid == default_category_id else ""
        rows.append([(f"{badge}📁 {name}", f"tgadm:wiz_cat:{cid}")])

    # "Пропустити" = поставити дефолтну категорію (Без категорії / перша)
    rows.append([("⏭ Пропустити", "tgadm:wiz_skip"), ("❌ Скасувати", "tgadm:cancel")])
    return _kb(rows)


def _state_get(tenant_id: str, chat_id: int) -> dict[str, Any] | None:
    return _STATE.get((tenant_id, chat_id))


def _state_set(tenant_id: str, chat_id: int, st: dict[str, Any]) -> None:
    _STATE[(tenant_id, chat_id)] = st


def _state_clear(tenant_id: str, chat_id: int) -> None:
    _STATE.pop((tenant_id, chat_id), None)


async def _send_admin_home(bot: Bot, chat_id: int) -> None:
    await bot.send_message(
        chat_id,
        "🛠 *Адмінка магазину*\n\nОдна точка входу — *📦 Каталог* 👇",
        parse_mode="Markdown",
        reply_markup=_admin_home_kb(),
    )


async def _send_catalog_home(bot: Bot, chat_id: int) -> None:
    await bot.send_message(
        chat_id,
        "📦 *Каталог*\n\nОбери розділ 👇",
        parse_mode="Markdown",
        reply_markup=_catalog_kb(),
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


async def _send_archive_list(bot: Bot, chat_id: int, tenant_id: str) -> None:
    if hasattr(ProductsRepo, "list_inactive"):
        items = await ProductsRepo.list_inactive(tenant_id, limit=100)  # type: ignore[attr-defined]
        if not items:
            await bot.send_message(chat_id, "🗃 Архів порожній (вимкнених товарів нема).")
            return
        lines = ["🗃 *Архів (вимкнені):*"]
        for p in items:
            lines.append(f"{int(p['id'])}) {p['name']} — {_fmt_money(int(p.get('price_kop') or 0))}")
        await bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")
        return

    await bot.send_message(
        chat_id,
        "🗃 *Архів (вимкнені)*\n\nПоки що в розробці (треба додати list_inactive у ProductsRepo).",
        parse_mode="Markdown",
        reply_markup=_catalog_kb(),
    )


# -----------------------------
# Wizard: name -> price -> desc -> category -> create -> photos -> done
# -----------------------------
async def _wiz_ask_name(bot: Bot, chat_id: int, tenant_id: str) -> None:
    _state_set(tenant_id, chat_id, {"mode": "wiz_name", "draft": {}})
    await bot.send_message(
        chat_id,
        "➕ *Новий товар*\n\n1/5 Введи *назву* товару:",
        parse_mode="Markdown",
        reply_markup=_wiz_nav_kb(),
    )


async def _wiz_ask_price(bot: Bot, chat_id: int, tenant_id: str, draft: dict) -> None:
    _state_set(tenant_id, chat_id, {"mode": "wiz_price", "draft": draft})
    await bot.send_message(
        chat_id,
        "2/5 Введи *ціну* (наприклад `1200.50` або `1200`):",
        parse_mode="Markdown",
        reply_markup=_wiz_nav_kb(),
    )


async def _wiz_ask_desc(bot: Bot, chat_id: int, tenant_id: str, draft: dict) -> None:
    _state_set(tenant_id, chat_id, {"mode": "wiz_desc", "draft": draft})
    await bot.send_message(
        chat_id,
        "3/5 Додай *опис* (або натисни `Пропустити`):",
        parse_mode="Markdown",
        reply_markup=_wiz_nav_kb(allow_skip=True),
    )


async def _wiz_ask_category(bot: Bot, chat_id: int, tenant_id: str, draft: dict) -> None:
    # Якщо категорійного репо ще нема — створюємо товар без категорії
    if CategoriesRepo is None:
        draft["category_id"] = None
        await _wiz_create_and_go_photos(bot, chat_id, tenant_id, draft)
        return

    # гарантовано створюємо "Без категорії" (або першу) і робимо backfill
    default_cid = await CategoriesRepo.ensure_default(tenant_id)  # type: ignore[misc]
    cats = await CategoriesRepo.list(tenant_id, limit=50)  # type: ignore[misc]

    # показуємо вибір
    _state_set(
        tenant_id,
        chat_id,
        {"mode": "wiz_category", "draft": draft, "default_category_id": int(default_cid or 0)},
    )
    await bot.send_message(
        chat_id,
        "4/5 *Категорія*\n\nОбери категорію для товару:",
        parse_mode="Markdown",
        reply_markup=_category_pick_kb(cats, default_category_id=int(default_cid or 0)),
    )


async def _wiz_create_product(tenant_id: str, draft: dict) -> int | None:
    name = str(draft.get("name") or "").strip()
    price_kop = int(draft.get("price_kop") or 0)
    desc = str(draft.get("description") or "").strip()

    category_id = draft.get("category_id", None)
    if isinstance(category_id, str) and category_id.isdigit():
        category_id = int(category_id)
    elif category_id is not None and not isinstance(category_id, int):
        category_id = None

    pid = await ProductsRepo.add(tenant_id, name, price_kop, is_active=True, category_id=category_id)
    if not pid:
        return None

    if desc:
        await ProductsRepo.set_description(tenant_id, int(pid), desc)

    return int(pid)


async def _wiz_create_and_go_photos(bot: Bot, chat_id: int, tenant_id: str, draft: dict) -> None:
    pid = await _wiz_create_product(tenant_id, draft)
    _state_clear(tenant_id, chat_id)
    if not pid:
        await bot.send_message(chat_id, "❌ Не вдалося створити товар (перевір БД/міграції).", reply_markup=_admin_home_kb())
        return
    await _wiz_photos_start(bot, chat_id, tenant_id, pid)


async def _wiz_photos_start(bot: Bot, chat_id: int, tenant_id: str, product_id: int) -> None:
    _state_set(tenant_id, chat_id, {"mode": "wiz_photo", "product_id": int(product_id)})
    await bot.send_message(
        chat_id,
        f"📷 Фото для товару *#{product_id}*\n\n"
        "Надсилай фото (можна кілька).\n"
        "Після кожного фото я спитаю — додати ще чи `Готово`.",
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
    photos = msg.get("photo") or []
    if photos:
        return str(photos[-1].get("file_id"))

    doc = msg.get("document")
    if doc:
        mime = (doc.get("mime_type") or "").lower()
        if mime.startswith("image/"):
            return str(doc.get("file_id"))

    return None


# -----------------------------
# Categories UI (minimal)
# -----------------------------
async def _send_categories_list(bot: Bot, chat_id: int, tenant_id: str) -> None:
    if CategoriesRepo is None:
        await bot.send_message(chat_id, "📁 Категорії ще не підключені (репо буде додано наступним кроком).")
        return

    await CategoriesRepo.ensure_default(tenant_id)  # type: ignore[misc]
    cats = await CategoriesRepo.list(tenant_id, limit=100)  # type: ignore[misc]

    if not cats:
        await bot.send_message(chat_id, "📁 Поки що немає категорій. Натисни ➕ Створити категорію.", reply_markup=_categories_menu_kb())
        return

    lines = ["📁 *Категорії:*"]
    for c in cats:
        lines.append(f"- {c['name']} (id={c['id']})")
    await bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown", reply_markup=_categories_menu_kb())


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
        arg = parts[2] if len(parts) > 2 else ""

        # HOME / CATALOG MENUS
        if action == "home":
            _state_clear(tenant_id, chat_id)
            await _send_admin_home(bot, chat_id)
            return True

        if action == "catalog":
            _state_clear(tenant_id, chat_id)
            await _send_catalog_home(bot, chat_id)
            return True

        if action == "prod_menu":
            _state_clear(tenant_id, chat_id)
            await bot.send_message(chat_id, "📦 *Товари*\n\nОбери дію 👇", parse_mode="Markdown", reply_markup=_products_menu_kb())
            return True

        if action == "cat_menu":
            _state_clear(tenant_id, chat_id)
            if CategoriesRepo is not None:
                await CategoriesRepo.ensure_default(tenant_id)  # type: ignore[misc]
            await bot.send_message(chat_id, "📁 *Категорії*\n\nОбери дію 👇", parse_mode="Markdown", reply_markup=_categories_menu_kb())
            return True

        if action == "archive":
            _state_clear(tenant_id, chat_id)
            await _send_archive_list(bot, chat_id, tenant_id)
            return True

        if action == "promos":
            _state_clear(tenant_id, chat_id)
            await bot.send_message(chat_id, "🔥 *Акції / Знижки*\n\nПоки що в розробці.", parse_mode="Markdown", reply_markup=_catalog_kb())
            return True

        if action == "cancel":
            _state_clear(tenant_id, chat_id)
            await bot.send_message(chat_id, "✅ Скасовано.", reply_markup=_admin_home_kb())
            return True

        # products list
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

        # Categories
        if action == "cat_list":
            _state_clear(tenant_id, chat_id)
            await _send_categories_list(bot, chat_id, tenant_id)
            return True

        if action == "cat_create":
            _state_set(tenant_id, chat_id, {"mode": "cat_create_name"})
            await bot.send_message(chat_id, "➕ Введи назву нової категорії:", reply_markup=_wiz_nav_kb())
            return True

        # Wizard
        if action == "wiz_start":
            await _wiz_ask_name(bot, chat_id, tenant_id)
            return True

        if action == "wiz_cat":
            st = _state_get(tenant_id, chat_id) or {}
            draft = st.get("draft") or {}
            if arg.isdigit():
                draft["category_id"] = int(arg)
            else:
                draft["category_id"] = None
            await _wiz_create_and_go_photos(bot, chat_id, tenant_id, draft)
            return True

        if action == "wiz_skip":
            st = _state_get(tenant_id, chat_id) or {}
            mode = st.get("mode")
            draft = st.get("draft") or {}

            if mode == "wiz_desc":
                draft["description"] = ""
                await _wiz_ask_category(bot, chat_id, tenant_id, draft)
                return True

            if mode == "wiz_category":
                default_cid = int(st.get("default_category_id") or 0)
                draft["category_id"] = default_cid if default_cid > 0 else None
                await _wiz_create_and_go_photos(bot, chat_id, tenant_id, draft)
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
            product_id = int(arg) if arg.isdigit() else int(st.get("product_id") or 0)
            if product_id <= 0:
                await bot.send_message(chat_id, "❌ Нема product_id. Відкрий wizard заново.", reply_markup=_admin_home_kb())
                return True
            await _wiz_photos_start(bot, chat_id, tenant_id, product_id)
            return True

        if action == "wiz_desc_edit":
            if not arg.isdigit():
                await bot.send_message(chat_id, "❌ Нема ID товару.", reply_markup=_admin_home_kb())
                return True
            pid = int(arg)
            _state_set(tenant_id, chat_id, {"mode": "desc_edit", "product_id": pid})
            await bot.send_message(chat_id, f"📝 Надішли новий опис для товару #{pid}:", reply_markup=_wiz_nav_kb(allow_skip=True))
            return True

        return False

    # ---------- messages ----------
    msg = _extract_message(data)
    if not msg:
        return False

    chat_id = int(msg["chat"]["id"])
    text = (msg.get("text") or "").strip()

    if text in ("/a", "/a_help"):
        await _send_admin_home(bot, chat_id)
        return True

    st = _state_get(tenant_id, chat_id)
    if not st:
        return False

    mode = str(st.get("mode") or "")

    # photo in wizard
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
                "Надішли *фото* (або файл-скрін, але як картинку). Або натисни `Готово`.",
                parse_mode="Markdown",
                reply_markup=_wiz_photos_kb(product_id=product_id),
            )
            return True

        await ProductsRepo.add_product_photo(tenant_id, product_id, file_id)

        await bot.send_message(
            chat_id,
            f"✅ Фото додано до *#{product_id}*.\n\nДодати ще чи `Готово`?",
            parse_mode="Markdown",
            reply_markup=_wiz_photos_kb(product_id=product_id),
        )
        return True

    # enable/disable by id
    if mode in ("enable", "disable"):
        if not text.isdigit():
            await bot.send_message(chat_id, "Надішли тільки цифру ID.")
            return True
        pid2 = int(text)
        await ProductsRepo.set_active(tenant_id, pid2, mode == "enable")
        _state_clear(tenant_id, chat_id)
        await bot.send_message(chat_id, f"✅ Товар {pid2} {'увімкнено' if mode=='enable' else 'вимкнено'}.", reply_markup=_admin_home_kb())
        return True

    # create category
    if mode == "cat_create_name":
        name = (text or "").strip()
        if not name:
            await bot.send_message(chat_id, "Назва категорії не може бути пустою.")
            return True

        if CategoriesRepo is None:
            _state_clear(tenant_id, chat_id)
            await bot.send_message(chat_id, "📁 Категорії ще не підключені (репо буде додано наступним кроком).", reply_markup=_catalog_kb())
            return True

        # ensure default exists first
        await CategoriesRepo.ensure_default(tenant_id)  # type: ignore[misc]
        cid = await CategoriesRepo.create(tenant_id, name[:64])  # type: ignore[misc]

        _state_clear(tenant_id, chat_id)
        await bot.send_message(chat_id, f"✅ Категорію створено: *{name}* (id={cid})", parse_mode="Markdown", reply_markup=_categories_menu_kb())
        return True

    # wizard steps
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
        await _wiz_ask_category(bot, chat_id, tenant_id, draft)
        return True

    # quick desc edit
    if mode == "desc_edit":
        product_id = int(st.get("product_id") or 0)
        if product_id <= 0:
            _state_clear(tenant_id, chat_id)
            await bot.send_message(chat_id, "❌ Нема ID товару.", reply_markup=_admin_home_kb())
            return True

        if text == "":
            await bot.send_message(chat_id, "Опис пустий. Можеш надіслати текст або натиснути Пропустити.", reply_markup=_wiz_nav_kb(allow_skip=True))
            return True

        await ProductsRepo.set_description(tenant_id, product_id, text)
        _state_clear(tenant_id, chat_id)
        await bot.send_message(chat_id, f"✅ Опис оновлено для #{product_id}.", reply_markup=_admin_home_kb())
        return True

    return False