from __future__ import annotations

from typing import Any

from aiogram import Bot

from rent_platform.modules.telegram_shop.repo.cart import TelegramShopCartRepo
from rent_platform.modules.telegram_shop.repo.orders import TelegramShopOrdersRepo
from rent_platform.modules.telegram_shop.repo.products import ProductsRepo
from rent_platform.modules.telegram_shop.ui.user_kb import BTN_CLEAR_CART, BTN_CHECKOUT


# -------------------------
# helpers
# -------------------------
def _fmt_money(kop: int) -> str:
    kop = int(kop or 0)
    uah = kop // 100
    cents = kop % 100
    return f"{uah}.{cents:02d} грн"


def _html_escape(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _kb(rows: list[list[tuple[str, str]]]) -> dict:
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for (t, d) in row] for row in rows]}


def _cart_list_kb(items: list[dict[str, Any]], *, cart_message_id: int) -> dict:
    """
    Інлайн під кошиком:
    - кнопки товарів (відкривають картку)
    - нижче: Очистити / Оформити
    """
    rows: list[list[tuple[str, str]]] = []

    for it in items:
        pid = int(it["product_id"])
        name = str(it.get("name") or "")
        qty = int(it.get("qty") or 0)

        title = name.strip()
        if len(title) > 28:
            title = title[:27] + "…"

        # cart_message_id потрібен, щоб "назад" оновлював саме цей кошик
        rows.append([(f"🛍 {title} ×{qty}", f"tgcart:open:{pid}:0:{cart_message_id}")])

    # дії кошика (без reply-клави і без "Дії кошика" повідомлення)
    rows.append(
        [
            ("🧹 Очистити", f"tgcart:clear:0:0:{cart_message_id}"),
            ("✅ Оформити", f"tgcart:checkout:0:0:{cart_message_id}"),
        ]
    )

    return _kb(rows)


def _cart_item_kb(product_id: int, qty: int, *, cart_message_id: int) -> dict:
    return _kb(
        [
            [
                ("➖", f"tgcart:inc:{product_id}:-1:{cart_message_id}"),
                (f"×{qty}", "tgcart:noop:0:0"),
                ("➕", f"tgcart:inc:{product_id}:1:{cart_message_id}"),
            ],
            [("🗑 Видалити", f"tgcart:del:{product_id}:0:{cart_message_id}")],
            [("⬅️ До кошика", f"tgcart:back:0:0:{cart_message_id}")],
        ]
    )


async def _render_cart(tenant_id: str, user_id: int) -> tuple[str, list[dict[str, Any]]]:
    items = await TelegramShopCartRepo.cart_list(tenant_id, user_id)

    if not items:
        return ("🛒 <b>Кошик</b>\n\nПоки що порожньо.", [])

    total_kop = 0
    saved_kop = 0
    lines: list[str] = []

    for it in items:
        name = _html_escape(str(it.get("name") or ""))
        qty = int(it.get("qty") or 0)

        eff = int(it.get("price_kop") or 0)          # effective unit
        base = int(it.get("base_price_kop") or eff)  # base unit

        eff_total = eff * qty
        base_total = base * qty

        total_kop += eff_total

        if base > eff:
            saved_kop += (base_total - eff_total)
            lines.append(
                f"• <b>{name}</b> ×{qty}\n"
                f"  <s>{_fmt_money(base_total)}</s> → <b>{_fmt_money(eff_total)}</b> 🔥"
            )
        else:
            lines.append(f"• <b>{name}</b> ×{qty} — <b>{_fmt_money(eff_total)}</b>")

    text = "🛒 <b>Кошик</b> ✨\n\n" + "\n".join(lines)
    text += "\n\n" + "──────────────"
    text += f"\n<b>Разом:</b> {_fmt_money(total_kop)} ✅"
    if saved_kop > 0:
        text += f"\n<b>Зекономлено:</b> {_fmt_money(saved_kop)} 🔥"

    return (text, items)


async def _edit_cart_message(
    bot: Bot,
    chat_id: int,
    cart_message_id: int,
    tenant_id: str,
    user_id: int,
) -> None:
    text, items = await _render_cart(tenant_id, user_id)

    if not items:
        await bot.edit_message_text(
            text,
            chat_id=chat_id,
            message_id=cart_message_id,
            parse_mode="HTML",
            reply_markup=None,
        )
        return

    await bot.edit_message_text(
        text,
        chat_id=chat_id,
        message_id=cart_message_id,
        parse_mode="HTML",
        reply_markup=_cart_list_kb(items, cart_message_id=cart_message_id),
    )


# -------------------------
# public API
# -------------------------
async def send_cart(bot: Bot, chat_id: int, tenant_id: str, user_id: int, *, extra_text: str = "") -> None:
    text, items = await _render_cart(tenant_id, user_id)

    if extra_text:
        text += f"\n\n{_html_escape(extra_text)}"

    # 1) відправляємо повідомлення (БЕЗ reply-клави)
    msg = await bot.send_message(
        chat_id,
        text,
        parse_mode="HTML",
    )

    # 2) чіпляємо inline-кнопки (вже можна, бо це inline)
    if items:
        await bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=msg.message_id,
            reply_markup=_cart_list_kb(items, cart_message_id=msg.message_id),
        )


async def handle_cart_message(
    *,
    bot: Bot,
    tenant_id: str,
    user_id: int,
    chat_id: int,
    text: str,
) -> bool:
    # На випадок якщо в когось ще лишились старі reply-кнопки
    if text == BTN_CLEAR_CART:
        await TelegramShopCartRepo.cart_clear(tenant_id, user_id)
        await send_cart(bot, chat_id, tenant_id, user_id, extra_text="Кошик очищено ✅")
        return True

    if text == BTN_CHECKOUT:
        oid = await TelegramShopOrdersRepo.create_order_from_cart(tenant_id, user_id)
        if not oid:
            await send_cart(bot, chat_id, tenant_id, user_id, extra_text="Кошик порожній.")
            return True
        await bot.send_message(chat_id, f"✅ Замовлення <b>#{oid}</b> створено!", parse_mode="HTML")
        return True

    return False


async def handle_cart_callback(
    *,
    bot: Bot,
    tenant_id: str,
    user_id: int,
    chat_id: int,
    message_id: int,
    payload: str,
) -> bool:
    """
    payload = callback_data
    tgcart:<action>:<arg>:<arg2>:<cart_message_id>
    """
    if not payload.startswith("tgcart:"):
        return False

    parts = payload.split(":")
    action = parts[1] if len(parts) > 1 else ""
    arg = parts[2] if len(parts) > 2 else ""
    arg2 = parts[3] if len(parts) > 3 else ""
    cart_mid_raw = parts[4] if len(parts) > 4 else "0"
    cart_message_id = int(cart_mid_raw) if cart_mid_raw.isdigit() else 0

    if action == "noop":
        return True

    if action == "back":
        try:
            await bot.delete_message(chat_id, message_id)
        except Exception:
            pass

        if cart_message_id > 0:
            try:
                await _edit_cart_message(bot, chat_id, cart_message_id, tenant_id, user_id)
                return True
            except Exception:
                pass

        await send_cart(bot, chat_id, tenant_id, user_id)
        return True

    if action == "clear":
        await TelegramShopCartRepo.cart_clear(tenant_id, user_id)
        if cart_message_id > 0:
            try:
                await _edit_cart_message(bot, chat_id, cart_message_id, tenant_id, user_id)
                return True
            except Exception:
                pass
        await send_cart(bot, chat_id, tenant_id, user_id, extra_text="Кошик очищено ✅")
        return True

    if action == "checkout":
        oid = await TelegramShopOrdersRepo.create_order_from_cart(tenant_id, user_id)
        if not oid:
            # просто оновимо кошик
            if cart_message_id > 0:
                try:
                    await _edit_cart_message(bot, chat_id, cart_message_id, tenant_id, user_id)
                except Exception:
                    pass
            await bot.send_message(chat_id, "🛒 Кошик порожній — нічого оформлювати.", parse_mode="HTML")
            return True

        await bot.send_message(chat_id, f"✅ Замовлення <b>#{oid}</b> створено!", parse_mode="HTML")

        # після оформлення cart вже очищений — оновлюємо кошик
        if cart_message_id > 0:
            try:
                await _edit_cart_message(bot, chat_id, cart_message_id, tenant_id, user_id)
                return True
            except Exception:
                pass

        await send_cart(bot, chat_id, tenant_id, user_id)
        return True

    if action == "open" and arg.isdigit():
        pid = int(arg)
        await _send_cart_item_card(
            bot,
            chat_id,
            tenant_id,
            user_id,
            pid,
            cart_message_id=cart_message_id,
        )
        return True

    if action == "inc" and arg.isdigit() and arg2.lstrip("-").isdigit():
        pid = int(arg)
        delta = int(arg2)
        qty = await TelegramShopCartRepo.cart_inc(tenant_id, user_id, pid, delta)

        if qty <= 0:
            try:
                await bot.delete_message(chat_id, message_id)
            except Exception:
                pass

            if cart_message_id > 0:
                try:
                    await _edit_cart_message(bot, chat_id, cart_message_id, tenant_id, user_id)
                    return True
                except Exception:
                    pass

            await send_cart(bot, chat_id, tenant_id, user_id, extra_text="Позицію видалено 🗑")
            return True

        await _edit_cart_item_card(
            bot,
            chat_id,
            message_id,
            tenant_id,
            user_id,
            pid,
            cart_message_id=cart_message_id,
            qty_override=qty,
        )

        if cart_message_id > 0:
            try:
                await _edit_cart_message(bot, chat_id, cart_message_id, tenant_id, user_id)
            except Exception:
                pass

        return True

    if action == "del" and arg.isdigit():
        pid = int(arg)
        await TelegramShopCartRepo.cart_delete_item(tenant_id, user_id, pid)

        try:
            await bot.delete_message(chat_id, message_id)
        except Exception:
            pass

        if cart_message_id > 0:
            try:
                await _edit_cart_message(bot, chat_id, cart_message_id, tenant_id, user_id)
                return True
            except Exception:
                pass

        await send_cart(bot, chat_id, tenant_id, user_id, extra_text="Позицію видалено 🗑")
        return True

    return True


# -------------------------
# internal: card render/edit
# -------------------------
async def _get_cart_item(tenant_id: str, user_id: int, product_id: int) -> dict[str, Any] | None:
    items = await TelegramShopCartRepo.cart_list(tenant_id, user_id)
    for it in items:
        if int(it.get("product_id") or 0) == int(product_id):
            return it
    return None


def _build_item_caption(it: dict[str, Any]) -> str:
    name = _html_escape(str(it.get("name") or ""))
    qty = int(it.get("qty") or 0)
    eff = int(it.get("price_kop") or 0)
    base = int(it.get("base_price_kop") or eff)

    unit_txt = _fmt_money(eff)
    total_txt = _fmt_money(eff * qty)

    text = f"<b>{name}</b>\n\n"
    text += f"К-сть: <b>{qty}</b>\n"

    if base > eff:
        text += f"Ціна: <s>{_fmt_money(base)}</s>  <b>{unit_txt}</b> 🔥\n"
        saved = (base - eff) * qty
        if saved > 0:
            text += f"Зекономлено: <b>{_fmt_money(saved)}</b> ✨\n"
    else:
        text += f"Ціна: <b>{unit_txt}</b>\n"

    text += f"\nСума: <b>{total_txt}</b> ✅"
    return text


async def _send_cart_item_card(
    bot: Bot,
    chat_id: int,
    tenant_id: str,
    user_id: int,
    product_id: int,
    *,
    cart_message_id: int,
) -> None:
    it = await _get_cart_item(tenant_id, user_id, product_id)
    if not it:
        await bot.send_message(chat_id, "Цієї позиції вже немає в кошику.", parse_mode="HTML")
        if cart_message_id > 0:
            try:
                await _edit_cart_message(bot, chat_id, cart_message_id, tenant_id, user_id)
                return
            except Exception:
                pass
        await send_cart(bot, chat_id, tenant_id, user_id)
        return

    qty = int(it.get("qty") or 0)
    caption = _build_item_caption(it)
    kb = _cart_item_kb(product_id, qty, cart_message_id=cart_message_id)

    cover = await ProductsRepo.get_cover_photo_file_id(tenant_id, product_id)

    if cover:
        await bot.send_photo(chat_id, photo=cover, caption=caption, parse_mode="HTML", reply_markup=kb)
    else:
        await bot.send_message(chat_id, caption, parse_mode="HTML", reply_markup=kb)


async def _edit_cart_item_card(
    bot: Bot,
    chat_id: int,
    message_id: int,
    tenant_id: str,
    user_id: int,
    product_id: int,
    *,
    cart_message_id: int,
    qty_override: int | None = None,
) -> None:
    it = await _get_cart_item(tenant_id, user_id, product_id)
    if not it:
        try:
            await bot.delete_message(chat_id, message_id)
        except Exception:
            pass
        if cart_message_id > 0:
            try:
                await _edit_cart_message(bot, chat_id, cart_message_id, tenant_id, user_id)
                return
            except Exception:
                pass
        await send_cart(bot, chat_id, tenant_id, user_id)
        return

    if qty_override is not None:
        it = dict(it)
        it["qty"] = int(qty_override)

    qty = int(it.get("qty") or 0)
    caption = _build_item_caption(it)
    kb = _cart_item_kb(product_id, qty, cart_message_id=cart_message_id)

    try:
        await bot.edit_message_caption(
            chat_id=chat_id,
            message_id=message_id,
            caption=caption,
            parse_mode="HTML",
            reply_markup=kb,
        )
        return
    except Exception:
        pass

    try:
        await bot.edit_message_text(
            caption,
            chat_id=chat_id,
            message_id=message_id,
            parse_mode="HTML",
            reply_markup=kb,
        )
    except Exception:
        await _send_cart_item_card(
            bot,
            chat_id,
            tenant_id,
            user_id,
            product_id,
            cart_message_id=cart_message_id,
        )