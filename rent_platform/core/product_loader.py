# rent_platform/core/product_loader.py
from __future__ import annotations

import importlib
from typing import Callable, Any

from rent_platform.products.catalog import PRODUCT_CATALOG


def _load_callable(path: str) -> Callable[..., Any]:
    """
    path format: "package.module:callable"
    """
    mod_path, fn_name = path.split(":", 1)
    mod = importlib.import_module(mod_path)
    fn = getattr(mod, fn_name)
    return fn


def get_active_product_key(tenant: dict) -> str | None:
    # основне джерело — product_key з БД
    pk = (tenant.get("product_key") or "").strip()
    return pk or None


def get_product_meta(product_key: str) -> dict | None:
    return PRODUCT_CATALOG.get(product_key)


def load_product_welcome(product_key: str) -> Callable[[dict], str] | None:
    meta = get_product_meta(product_key)
    if not meta:
        return None
    welcome_path = meta.get("welcome")
    if not welcome_path:
        return None
    fn = _load_callable(welcome_path)
    return fn  # type: ignore


def load_product_handler(product_key: str):
    meta = get_product_meta(product_key)
    if not meta:
        return None
    handler_path = meta.get("handler")
    if not handler_path:
        return None
    return _load_callable(handler_path)