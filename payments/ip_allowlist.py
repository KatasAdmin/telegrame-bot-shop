# -*- coding: utf-8 -*-
from __future__ import annotations

import ipaddress


def ip_allowed(ip: str, allowed: str) -> bool:
    if not ip or not allowed:
        return False

    try:
        ip_obj = ipaddress.ip_address(ip)
    except Exception:
        return False

    for part in allowed.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            if "/" in part:
                if ip_obj in ipaddress.ip_network(part, strict=False):
                    return True
            else:
                if ip_obj == ipaddress.ip_address(part):
                    return True
        except Exception:
            continue

    return False