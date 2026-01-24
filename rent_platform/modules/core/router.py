from __future__ import annotations

from aiogram import Bot

from rent_platform.shared.utils import send_message
from rent_platform.products.catalog import PRODUCT_CATALOG


def _extract_message(update: dict) -> dict | None:
    # підтримка message + callback_query.message
    msg = update.get("message")
    if msg:
        return msg
    cb = update.get("callback_query")
    if cb and cb.get("message"):
        return cb["message"]
    return None


def _extract_text(update: dict) -> str:
    msg = update.get("message")
    if msg and msg.get("text"):
        return (msg.get("text") or "").strip()

    cb = update.get("callback_query")
    if cb and cb.get("data"):
        return (cb.get("data") or "").strip()

    return ""


def _extract_chat_id(msg: dict) -> int | None:
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    return int(chat_id) if chat_id is not None else None


def _default_welcome_text() -> str:
    return (
        "✅ <b>Орендований бот активний</b>\n\n"
        "Сервісні:\n"
        "• /ping — перевірка звʼязку\n"
        "• /help — підказка\n"
    )


def _module_manifest_commands(module_key: str) -> list[tuple[str, str]]:
    """
    Повертає команди з MANIFEST.commands якщо він є.
    Формат: [(cmd, desc), ...]
    """
    try:
        # важливо: в модулях має бути manifest.py
        # наприклад rent_platform.modules.telegram_shop.manifest
        mod = __import__(f"rent_platform.modules.{module_key}.manifest", fromlist=["MANIFEST"])
        manifest = getattr(mod, "MANIFEST", None) or {}
        cmds = manifest.get("commands") or []
        out: list[tuple[str, str]] = []
        for item in cmds:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                c, d = item
                out.append((str(c), str(d)))
        return out
    except Exception:
        return []


def _product_block(tenant: dict) -> str:
    """
    Формує опис продукту з PRODUCT_CATALOG по tenant.product_key.
    """
    product_key = (tenant.get("product_key") or "").strip()
    if not product_key:
        return ""

    meta = PRODUCT_CATALOG.get(product_key)
    if not meta:
        return ""

    title = (meta.get("title") or "").strip()
    desc = (meta.get("desc") or "").strip()

    # desc у тебе вже HTML — ок
    if title and desc:
        return f"🧩 <b>Продукт:</b> {title}\n\n{desc}\n"
    if title:
        return f"🧩 <b>Продукт:</b> {title}\n"
    if desc:
        return f"{desc}\n"
    return ""


def _commands_block(tenant: dict) -> str:
    """
    Команди формуємо з manifest активного продуктового модуля (module_key == product_key).
    Якщо нема — порожньо.
    """
    product_key = (tenant.get("product_key") or "").strip()
    if not product_key:
        return ""

    cmds = _module_manifest_commands(product_key)
    if not cmds:
        return ""

    lines = ["Доступні команди:"]
    for c, d in cmds:
        lines.append(f"• {c} — {d}")
    return "\n".join(lines) + "\n"


def _welcome_text(tenant: dict) -> str:
    base = _default_welcome_text()

    product = _product_block(tenant)
    commands = _commands_block(tenant)

    text = "✅ <b>Орендований бот активний</b>\n\n"

    # якщо є продукт — показуємо його
    if product:
        text += product + "\n"

    # якщо є команди з маніфесту — показуємо їх, інакше нічого не вигадуємо
    if commands:
        text += commands + "\n"

    # сервісні — завжди
    text += "Сервісні:\n• /ping — перевірка звʼязку\n• /help — підказка\n"
    return text


async def handle_update(tenant: dict, update: dict, bot: Bot) -> bool:
    msg = _extract_message(update)
    if not msg:
        return False

    chat_id = _extract_chat_id(msg)
    if not chat_id:
        return False

    text = _extract_text(update)

    # --- базові команди ---
    if text in ("/start", "/help"):
        await send_message(bot, chat_id, _welcome_text(tenant))
        return True

    if text == "/ping":
        await send_message(bot, chat_id, "pong ✅")
        return True

    # --- fallback: якщо користувач пише щось незрозуміле ---
    # не перехоплюємо будь-які команди інших модулів — хай вони самі вирішують.
    if text and text.startswith("/"):
        await send_message(
            bot,
            chat_id,
            "Не знаю цю команду 🤝\n\n" + _welcome_text(tenant),
        )
        return True

    return False