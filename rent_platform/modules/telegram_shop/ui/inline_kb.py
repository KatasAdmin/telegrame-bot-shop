from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def catalog_inline(*, product_ids: list[int]) -> InlineKeyboardMarkup:
    """
    Catalog: for each product -> [➕ Add]
    plus: [🛒 Cart]
    """
    rows: list[list[InlineKeyboardButton]] = []
    for pid in product_ids:
        rows.append([_btn(f"➕ Додати #{pid}", f"tgshop:add:{pid}")])
    rows.append([_btn("🛒 Кошик", "tgshop:cart")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cart_inline(*, items: list[dict]) -> InlineKeyboardMarkup:
    """
    Cart: per item controls: [➖][qty][➕][🗑]
    plus: [✅ Checkout] [🧹 Clear] [🛍 Catalog]
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
    rows.append([_btn("🛍 Каталог", "tgshop:catalog")])
    return InlineKeyboardMarkup(inline_keyboard=rows)