from __future__ import annotations

from typing import Any

from rent_platform.modules.telegram_shop.admin.handlers import (
    handle_update as admin_handle_update,
    admin_has_state,
)


def is_admin_user(*, tenant: dict[str, Any], user_id: int) -> bool:
    try:
        owner_id = int(tenant.get("owner_user_id") or 0)
    except Exception:
        owner_id = 0

    if owner_id and int(user_id) == owner_id:
        return True

    extra = tenant.get("admin_user_ids") or []
    try:
        return int(user_id) in {int(x) for x in extra}
    except Exception:
        return False


__all__ = ["admin_handle_update", "admin_has_state", "is_admin_user"]