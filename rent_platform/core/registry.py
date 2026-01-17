# rent_platform/core/registry.py

from typing import Callable

MODULES: dict[str, Callable] = {}


def register_module(name: str, router_factory: Callable):
    MODULES[name] = router_factory


def get_module(name: str):
    return MODULES.get(name)

# rent_platform/core/registry.py

from rent_platform.modules.shop.router import handle_update as shop_handler

MODULES = {}

def register_module(name: str, router_factory):
    MODULES[name] = router_factory


def get_module(name: str):
    return MODULES.get(name)


# 🔥 РЕЄСТРАЦІЯ МОДУЛІВ
register_module("shop", shop_handler)