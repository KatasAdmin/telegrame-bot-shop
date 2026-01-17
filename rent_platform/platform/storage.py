from __future__ import annotations

import secrets
from dataclasses import dataclass, asdict
from typing import Dict, List


@dataclass
class UserBot:
    id: str
    token: str
    name: str = "Bot"
    created_ts: int | None = None


# Поки що просте сховище в RAM:
# user_id -> list[UserBot]
_USER_BOTS: Dict[int, List[UserBot]] = {}


def list_bots(user_id: int) -> list[dict]:
    items = _USER_BOTS.get(user_id, [])
    return [asdict(x) for x in items]


def add_bot(user_id: int, token: str, name: str = "Bot") -> dict:
    bot_id = secrets.token_hex(4)  # короткий id
    item = UserBot(id=bot_id, token=token, name=name)
    _USER_BOTS.setdefault(user_id, []).append(item)
    return asdict(item)


def delete_bot(user_id: int, bot_id: str) -> bool:
    items = _USER_BOTS.get(user_id, [])
    before = len(items)
    items = [x for x in items if x.id != bot_id]
    _USER_BOTS[user_id] = items
    return len(items) != before