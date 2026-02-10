# -*- coding: utf-8 -*-
from __future__ import annotations


def parse_allowlist(raw: str) -> set[str]:
    raw = (raw or "").strip()
    if not raw:
        return set()
    parts = [p.strip() for p in raw.replace("\n", ",").split(",")]
    return {p for p in parts if p}


def is_ip_allowed(remote_ip: str, allow: set[str]) -> bool:
    if not allow:
        return True  # if allowlist empty -> allow all
    return remote_ip in allow