єfrom __future__ import annotations

from typing import Any

from rent_platform.modules.telegram_shop.admin.handlers import handle_update as admin_handle_update


def is_admin_user(*, tenant: dict[str, Any], user_id: int) -> bool:
    """
    Мінімальна, але надійна перевірка адміна.
    - owner_user_id (основний адмін)
    - або admin_user_ids (якщо колись додаси список)
    """
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


__all__ = ["admin_handle_update", "is_admin_user"]