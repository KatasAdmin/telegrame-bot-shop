from __future__ import annotations

from typing import Any

from aiogram import Bot

from rent_platform.modules.telegram_shop.repo.cart import TelegramShopCartRepo
from rent_platform.modules.telegram_shop.repo.products import ProductsRepo
from rent_platform.modules.telegram_shop.repo.orders import TelegramShopOrdersRepo
from rent_platform.modules.telegram_shop.ui.user_kb import cart_kb, BTN_CLEAR_CART, BTN_CHECKOUT


# -------------------------
# helpers
# -------------------------
def _fmt_money(kop: int) -> str:
    kop = int(kop or 0)
    uah = kop // 100
    cents = kop % 100
    return f"{uah}.{cents:02d} грн"


def _html_escape(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _kb(rows: list[list[tuple[str, str]]]) -> dict:
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for (t, d) in row] for row in rows]}


def _cart_list_kb(items: list[dict[str, Any]]) -> dict:
    rows: list[list[tuple[str, str]]] = []
    for it in items:
        pid = int(it["product_id"])
        name = str(it.get("name") or "")
        qty = int(it.get("qty") or 0)

        title = name.strip()
        if len(title) > 28:
            title = title[:27] + "…"

        rows.append([(f"🛍 {title} ×{qty}", f"tgcart:open:{pid}")])

    return _kb(rows)


def _cart_item_kb(product_id: int, qty: int) -> dict:
    return _kb(
        [
            [("➖", f"tgcart:inc:{product_id}:-1"), (f"×{qty}", "tgcart:noop"), ("➕", f"tgcart:inc:{product_id}:1")],
            [("🗑 Видалити", f"tgcart:del:{product_id}")],
            [("⬅️ До кошика", "tgcart:back")],
        ]
    )


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
        text += f"Ціна: <s>{_fmt_money(base)}</s>  <b>{unit_txt}</b>\n"
        saved = (base - eff) * qty
        if saved > 0:
            text += f"Зекономлено: <b>{_fmt_money(saved)}</b> 🔥\n"
    else:
        text += f"Ціна: <b>{unit_txt}</b>\n"

    text += f"\nСума: <b>{total_txt}</b>"
    return text


# -------------------------
# public API
# -------------------------
async def send_cart(
    bot: Bot,
    chat_id: int,
    tenant_id: str,
    user_id: int,
    *,
    extra_text: str = "",
    show_actions: bool = True,
) -> None:
    items = await TelegramShopCartRepo.cart_list(tenant_id, user_id)

    if not items:
        await bot.send_message(
            chat_id,
            "🛒 <b>Кошик</b>\n\nПоки що порожньо.",
            parse_mode="HTML",
            reply_markup=(cart_kb() if show_actions else None),
        )
        return

    total_kop = 0
    saved_kop = 0

    lines: list[str] = []
    for it in items:
        name = _html_escape(str(it.get("name") or ""))
        qty = int(it.get("qty") or 0)
        eff = int(it.get("price_kop") or 0)
        base = int(it.get("base_price_kop") or eff)

        line_total = eff * qty
        total_kop += line_total

        if base > eff:
            saved_kop += (base - eff) * qty

        lines.append(f"• {name} ×{qty} — <b>{_fmt_money(line_total)}</b>")

    text = "🛒 <b>Кошик</b>\n\n" + "\n".join(lines)
    text += f"\n\n<b>Разом:</b> {_fmt_money(total_kop)}"
    if saved_kop > 0:
        text += f"\n<b>Зекономлено:</b> {_fmt_money(saved_kop)} 🔥"

    if extra_text:
        text += f"\n\n{_html_escape(extra_text)}"

    # 1) головне повідомлення: список + кнопки товарів
    await bot.send_message(
        chat_id,
        text,
        parse_mode="HTML",
        reply_markup=_cart_list_kb(items),
    )

    # 2) один раз “прикріплюємо” ReplyKeyboard для дій кошика
    if show_actions:
        await bot.send_message(
            chat_id,
            "Дії кошика 👇",
            reply_markup=cart_kb(),
        )


async def handle_cart_message(
    *,
    bot: Bot,
    tenant_id: str,
    user_id: int,
    chat_id: int,
    text: str,
) -> bool:
    if text == BTN_CLEAR_CART:
        await TelegramShopCartRepo.cart_clear(tenant_id, user_id)
        await send_cart(bot, chat_id, tenant_id, user_id, extra_text="Кошик очищено ✅", show_actions=True)
        return True

    if text == BTN_CHECKOUT:
        oid = await TelegramShopOrdersRepo.create_order_from_cart(tenant_id, user_id)
        if not oid:
            await send_cart(bot, chat_id, tenant_id, user_id, extra_text="Кошик порожній.", show_actions=True)
            return True

        await bot.send_message(
            chat_id,
            f"✅ Замовлення <b>#{oid}</b> створено!",
            parse_mode="HTML",
            reply_markup=cart_kb(),
        )
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
    if not payload.startswith("tgcart:"):
        return False

    parts = payload.split(":")
    action = parts[1] if len(parts) > 1 else ""
    arg = parts[2] if len(parts) > 2 else ""
    arg2 = parts[3] if len(parts) > 3 else ""

    if action == "noop":
        return True

    if action == "back":
        try:
            await bot.delete_message(chat_id, message_id)
        except Exception:
            pass
        await send_cart(bot, chat_id, tenant_id, user_id, show_actions=False)
        return True

    if action == "open" and arg.isdigit():
        pid = int(arg)
        await _send_cart_item_card(bot, chat_id, tenant_id, user_id, pid)
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
            await send_cart(bot, chat_id, tenant_id, user_id, extra_text="Позицію видалено 🗑", show_actions=False)
            return True

        await _edit_cart_item_card(bot, chat_id, message_id, tenant_id, user_id, pid, qty_override=qty)
        return True

    if action == "del" and arg.isdigit():
        pid = int(arg)
        await TelegramShopCartRepo.cart_delete_item(tenant_id, user_id, pid)
        try:
            await bot.delete_message(chat_id, message_id)
        except Exception:
            pass
        await send_cart(bot, chat_id, tenant_id, user_id, extra_text="Позицію видалено 🗑", show_actions=False)
        return True

    return True


# -------------------------
# internal: card render/edit
# -------------------------
async def _send_cart_item_card(bot: Bot, chat_id: int, tenant_id: str, user_id: int, product_id: int) -> None:
    it = await _get_cart_item(tenant_id, user_id, product_id)
    if not it:
        await bot.send_message(chat_id, "Цієї позиції вже немає в кошику.", parse_mode="HTML")
        await send_cart(bot, chat_id, tenant_id, user_id, show_actions=False)
        return

    qty = int(it.get("qty") or 0)
    caption = _build_item_caption(it)
    kb = _cart_item_kb(product_id, qty)

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
    qty_override: int | None = None,
) -> None:
    it = await _get_cart_item(tenant_id, user_id, product_id)
    if not it:
        try:
            await bot.delete_message(chat_id, message_id)
        except Exception:
            pass
        await send_cart(bot, chat_id, tenant_id, user_id, show_actions=False)
        return

    if qty_override is not None:
        it = dict(it)
        it["qty"] = int(qty_override)

    qty = int(it.get("qty") or 0)
    caption = _build_item_caption(it)
    kb = _cart_item_kb(product_id, qty)

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
        await _send_cart_item_card(bot, chat_id, tenant_id, user_id, product_id)