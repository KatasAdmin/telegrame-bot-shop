from __future__ import annotations

from rent_platform.core.registry import register_module
from rent_platform.modules.shop.router import handle_update

register_module("shop", handle_update)