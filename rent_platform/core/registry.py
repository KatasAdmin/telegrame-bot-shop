# rent_platform/core/registry.py

from typing import Callable

MODULES: dict[str, Callable] = {}


def register_module(name: str, router_factory: Callable):
    MODULES[name] = router_factory


def get_module(name: str):
    return MODULES.get(name)