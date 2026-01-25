from __future__ import annotations

from rent_platform.modules.telegram_shop.admin.handlers import handle_update as admin_handle_update
from rent_platform.modules.telegram_shop.admin.acl import is_admin_user

__all__ = ["admin_handle_update", "is_admin_user"]