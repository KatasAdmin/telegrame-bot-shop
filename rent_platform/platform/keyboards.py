from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# === Тексти кнопок (одним місцем) ===
BTN_MARKETPLACE = "🧩 Маркетплейс"
BTN_MY_BOTS = "🤖 Мої боти"
BTN_CABINET = "👤 Кабінет"
BTN_PARTNERS = "🤝 Партнери"
BTN_HELP = "🆘 Підтримка"

BTN_ADMIN = "🛠 Адмінка (скоро)"


# Common labels
LBL_MENU = "⬅️ В меню"
LBL_BACK = "⬅️ Назад"
LBL_REFRESH = "🔄 Оновити"


def main_menu_kb(is_admin: bool = False) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text=BTN_MARKETPLACE), KeyboardButton(text=BTN_MY_BOTS)],
        [KeyboardButton(text=BTN_CABINET), KeyboardButton(text=BTN_PARTNERS)],
        [KeyboardButton(text=BTN_HELP)],
    ]
    if is_admin:
        keyboard.append([KeyboardButton(text=BTN_ADMIN)])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Обери розділ 👇",
    )


def main_menu_inline_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text=BTN_MARKETPLACE, callback_data="pl:marketplace"),
        InlineKeyboardButton(text=BTN_MY_BOTS, callback_data="pl:my_bots"),
        width=2,
    )
    kb.row(
        InlineKeyboardButton(text=BTN_CABINET, callback_data="pl:cabinet"),
        InlineKeyboardButton(text=BTN_PARTNERS, callback_data="pl:partners"),
        width=2,
    )
    kb.row(InlineKeyboardButton(text=BTN_HELP, callback_data="pl:support"), width=1)
    return kb.as_markup()


def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=LBL_MENU, callback_data="pl:menu")]])


# =========================================================
# Partners
# =========================================================
def partners_inline_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="🔗 Реф-силка", callback_data="pl:partners:link"),
        InlineKeyboardButton(text="📊 Статистика", callback_data="pl:partners:stats"),
        width=2,
    )
    kb.row(
        InlineKeyboardButton(text="💸 Виплати", callback_data="pl:partners:payouts"),
        InlineKeyboardButton(text="📜 Правила", callback_data="pl:partners:rules"),
        width=2,
    )
    kb.row(InlineKeyboardButton(text=LBL_MENU, callback_data="pl:menu"))
    return kb.as_markup()


def about_inline_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="ℹ️ Про платформу", callback_data="pl:about"),
        InlineKeyboardButton(text="🔒 Privacy policy", callback_data="pl:privacy"),
        width=1,
    )
    kb.row(
        InlineKeyboardButton(text="📄 Terms", callback_data="pl:terms"),
        InlineKeyboardButton(text="🛡 Commitments", callback_data="pl:commitments"),
        width=1,
    )
    kb.row(InlineKeyboardButton(text=LBL_MENU, callback_data="pl:menu"))
    return kb.as_markup()


# =========================================================
# кабінет
def cabinet_actions_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="💳 Поповнити", callback_data="pl:topup:start"),
        InlineKeyboardButton(text="💵 Вивести", callback_data="pl:cabinet:withdraw"),
        width=2,
    )
    kb.row(
        InlineKeyboardButton(text="♻️ Обміняти", callback_data="pl:cabinet:exchange"),
        InlineKeyboardButton(text="📈 Тарифи", callback_data="pl:cabinet:tariffs"),
        width=2,
    )
    kb.row(InlineKeyboardButton(text="📋 Історія", callback_data="pl:cabinet:history"), width=1)
    kb.row(InlineKeyboardButton(text="⬅️ В меню", callback_data="pl:menu"), width=1)
    return kb.as_markup()

# =========================================================
# My bots
# =========================================================
def my_bots_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="➕ Add bot //", callback_data="pl:my_bots:add"), width=1)
    kb.row(InlineKeyboardButton(text=f"{LBL_REFRESH} //", callback_data="pl:my_bots:refresh"), width=1)
    kb.row(InlineKeyboardButton(text=LBL_MENU, callback_data="pl:menu"), width=1)
    return kb.as_markup()


def _bot_badge(it: dict) -> str:
    st = (it.get("status") or "active").lower()
    pr = (it.get("paused_reason") or "").lower()

    if st == "active":
        return "🟢 online"
    if st == "paused":
        if pr == "billing":
            return "🔻 paused(billing)"
        if pr == "manual":
            return "🟡 paused(manual)"
        return "⏸ paused"
    if st == "deleted":
        return "🗑 deleted"
    return st


def my_bots_list_kb(items: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()

    for it in items:
        bot_id = it["id"]
        name = (it.get("name") or "Bot").strip()
        badge = _bot_badge(it)

        kb.row(
            InlineKeyboardButton(
                text=f"🤖 {name} — {badge}",
                callback_data=f"pl:my_bots:noop:{bot_id}",
            )
        )

        st = (it.get("status") or "active").lower()
        if st in ("active", "paused"):
            kb.row(
                InlineKeyboardButton(text="⚙️ Config //", callback_data=f"pl:cfg:open:{bot_id}"),
                InlineKeyboardButton(
                    text=("⏸ Pause //" if st == "active" else "▶️ Resume //"),
                    callback_data=(f"pl:my_bots:pause:{bot_id}" if st == "active" else f"pl:my_bots:resume:{bot_id}"),
                ),
                width=2,
            )
            kb.row(
                InlineKeyboardButton(text="🗑 Delete //", callback_data=f"pl:my_bots:del:{bot_id}"),
                width=1,
            )
        else:
            kb.row(InlineKeyboardButton(text="🙂 (disabled)", callback_data=f"pl:my_bots:noop:{bot_id}"))

    kb.row(InlineKeyboardButton(text="⬅️ Back //", callback_data="pl:my_bots"), width=1)
    return kb.as_markup()


# =========================================================
# Marketplace (products)
# mkp-flow only:
#   pl:mkp:open:<product_key>
#   pl:mkp:buy:<product_key>
# =========================================================
def marketplace_products_kb(items: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for it in items:
        key = it["key"]
        title = (it.get("title") or key).strip()

        rpm = it.get("rate_per_min_uah", None)
        if rpm is not None:
            try:
                title_btn = f"{title}  •  {float(rpm):.2f} грн/хв"
            except Exception:
                title_btn = title
        else:
            title_btn = title

        kb.row(InlineKeyboardButton(text=title_btn, callback_data=f"pl:mkp:open:{key}"))

    kb.row(InlineKeyboardButton(text=LBL_MENU, callback_data="pl:menu"))
    return kb.as_markup()


def marketplace_buy_kb(product_key: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✅ Buy // create copy", callback_data=f"pl:mkp:buy:{product_key}"))
    kb.row(InlineKeyboardButton(text="⬅️ Back //", callback_data="pl:marketplace"))
    kb.row(InlineKeyboardButton(text=LBL_MENU, callback_data="pl:menu"))
    return kb.as_markup()


# =========================================================
# TopUp (balance)
# =========================================================
def cabinet_topup_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="💰 TopUp //", callback_data="pl:topup:start"))
    kb.row(InlineKeyboardButton(text=LBL_MENU, callback_data="pl:menu"))
    return kb.as_markup()


def topup_provider_kb(amount_uah: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🏦 Mono", callback_data=f"pl:topup:prov:mono:{amount_uah}"))
    kb.row(InlineKeyboardButton(text="🏦 Privat", callback_data=f"pl:topup:prov:privat:{amount_uah}"))
    kb.row(InlineKeyboardButton(text="🪙 CryptoBot", callback_data=f"pl:topup:prov:cryptobot:{amount_uah}"))
    kb.row(InlineKeyboardButton(text=LBL_MENU, callback_data="pl:menu"))
    return kb.as_markup()


def topup_confirm_kb(invoice_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✅ Confirm paid (test) //", callback_data=f"pl:topup:confirm:{invoice_id}"))
    kb.row(InlineKeyboardButton(text=LBL_MENU, callback_data="pl:menu"))
    return kb.as_markup()


# =========================================================
# Cabinet pay (старе / можна лишити)
# =========================================================
def cabinet_pay_kb(bot_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="💳 Pay (1 month) //", callback_data=f"pl:pay:{bot_id}:1"))
    kb.row(InlineKeyboardButton(text=LBL_MENU, callback_data="pl:menu"))
    return kb.as_markup()


# =========================================================
# Config (tenant keys)
# =========================================================
def config_kb(bot_id: str, providers: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()

    for p in providers:
        prov = p["provider"]
        title = p["title"]
        enabled = bool(p["enabled"])
        kb.row(
            InlineKeyboardButton(
                text=f"{'✅' if enabled else '➕'} {title} //",
                callback_data=f"pl:cfg:tg:{bot_id}:{prov}",
            )
        )
        for s in p.get("secrets") or []:
            kb.row(
                InlineKeyboardButton(
                    text=f"🔑 {s['label']}",
                    callback_data=f"pl:cfg:set:{bot_id}:{s['key']}",
                )
            )

    kb.row(
        InlineKeyboardButton(text=f"{LBL_REFRESH} //", callback_data=f"pl:cfg:open:{bot_id}"),
        InlineKeyboardButton(text="⬅️ To bots //", callback_data="pl:my_bots"),
        width=2,
    )
    kb.row(InlineKeyboardButton(text=LBL_MENU, callback_data="pl:menu"))
    return kb.as_markup()