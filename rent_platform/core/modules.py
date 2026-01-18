# rent_platform/core/modules.py
from __future__ import annotations

import importlib
import logging

from rent_platform.core.registry import register_module
from rent_platform.products.catalog import PRODUCT_CATALOG

log = logging.getLogger(__name__)


def _load_handler(handler_path: str):
    """
    handler_path format: "package.module:callable"
    """
    mod_path, fn_name = handler_path.split(":", 1)
    mod = importlib.import_module(mod_path)
    fn = getattr(mod, fn_name)
    return fn


def init_modules() -> None:
    # core (завжди)
    try:
        from rent_platform.modules.core.router import handle_update as core_handler
        register_module("core", core_handler)
    except Exception as e:
        log.exception("Failed to init module 'core': %s", e)
        raise

    # products from catalog (авто)
    for product_key, meta in PRODUCT_CATALOG.items():
        module_key = meta.get("module_key")
        handler_path = meta.get("handler")

        if not module_key or not handler_path:
            log.warning("Product %s missing module_key/handler, skip", product_key)
            continue

        try:
            handler = _load_handler(handler_path)
            register_module(module_key, handler)
            log.info("Module registered: %s (product=%s)", module_key, product_key)
        except Exception as e:
            log.exception("Failed to init product module '%s' (product=%s): %s", module_key, product_key, e)
            raise