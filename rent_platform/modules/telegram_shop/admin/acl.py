from __future__ import annotations

import os


def is_admin_user(*, tenant: dict, user_id: int) -> bool:
    """
    Hook for admin resolution.
    TODAY: can read env ADMIN_USER_IDS="1,2,3" (simple)
    TOMORROW: read from tenant settings / platform cabinet / DB table etc.
    """
    # future hook: tenant-based admins
    # e.g. tenant.get("admin_user_ids") or tenant config

    raw = (os.getenv("ADMIN_USER_IDS") or "").strip()
    if not raw:
        return False

    allowed = {int(x.strip()) for x in raw.split(",") if x.strip().isdigit()}
    return int(user_id) in allowed