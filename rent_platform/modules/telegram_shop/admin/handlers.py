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


async def handle_update(*, tenant: dict, data: dict[str, Any], bot: Bot) -> bool:
    """
    Admin-only update handler.
    Return True if handled.
    """
    msg = data.get("message") or data.get("edited_message")
    if not msg:
        return False
    text = (msg.get("text") or "").strip()
    if not text:
        return False

    chat_id = int(msg["chat"]["id"])
    tenant_id = str(tenant["id"])

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

    return False