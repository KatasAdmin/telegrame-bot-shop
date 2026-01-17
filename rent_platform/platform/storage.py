# rent_platform/platform/storage.py
from __future__ import annotations

import secrets
from dataclasses import dataclass, asdict
from typing import Dict, List

from rent_platform.core.tenant_ctx import upsert_tenant


@dataclass
class UserBot:
    id: str
    token: str
    secret: str
    name: str = "Bot"
    active_modules: list[str] | None = None
    created_ts: int | None = None


# user_id -> list[UserBot]
_USER_BOTS: Dict[int, List[UserBot]] = {}


def list_bots(user_id: int) -> list[dict]:
    items = _USER_BOTS.get(user_id, [])
    return [asdict(x) for x in items]


def add_bot(user_id: int, token: str, name: str = "Bot") -> dict:
    bot_id = secrets.token_hex(4)      # короткий id
    secret = secrets.token_urlsafe(16) # секрет для webhook URL
    active_modules = ["shop"]          # дефолтний набір

    item = UserBot(id=bot_id, token=token, secret=secret, name=name, active_modules=active_modules)
    _USER_BOTS.setdefault(user_id, []).append(item)

    # ✅ реєстрація tenant (поки в RAM)
    upsert_tenant(
        tenant_id=bot_id,
        bot_token=token,
        secret=secret,
        active_modules=active_modules,
    )

    return asdict(item)


def delete_bot(user_id: int, bot_id: str) -> bool:
    items = _USER_BOTS.get(user_id, [])
    before = len(items)
    items = [x for x in items if x.id != bot_id]
    _USER_BOTS[user_id] = items
    return len(items) != before