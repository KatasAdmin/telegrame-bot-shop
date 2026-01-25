from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def product_card_kb(*, product_id: int, has_prev: bool, has_next: bool) -> InlineKeyboardMarkup:
    """
    Product card inline keyboard:
    - Add to cart / Favorites
    - Navigation: ◀️  •  ▶️
      If no prev/next => show • instead.
    """
    rows: list[list[InlineKeyboardButton]] = []

    rows.append([
        _btn("🛒 Додати в кошик", f"tgshop:add:{product_id}"),
        _btn("⭐ В обране", f"tgshop:fav:{product_id}"),
    ])

    rows.append([
        _btn("◀️", f"tgshop:prev:{product_id}") if has_prev else _btn("•", f"tgshop:noop:{product_id}"),
        _btn("•", f"tgshop:noop:{product_id}"),
        _btn("▶️", f"tgshop:next:{product_id}") if has_next else _btn("•", f"tgshop:noop:{product_id}"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def cart_inline(*, items: list[dict]) -> InlineKeyboardMarkup:
    """
    Cart controls (qty UI: ➖ qty ➕ 🗑) + checkout/clear
    """
    rows: list[list[InlineKeyboardButton]] = []
    for it in items:
        pid = int(it["product_id"])
        qty = int(it["qty"])
        rows.append([
            _btn("➖", f"tgshop:dec:{pid}"),
            _btn(f"{qty}", f"tgshop:noop:{pid}"),
            _btn("➕", f"tgshop:inc:{pid}"),
            _btn("🗑", f"tgshop:del:{pid}"),
        ])

    rows.append([
        _btn("✅ Оформити", "tgshop:checkout"),
        _btn("🧹 Очистити", "tgshop:clear"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)