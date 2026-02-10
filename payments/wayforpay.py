# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any


def _sign(secret: str, fields: list[str]) -> str:
    raw = ";".join(fields)
    return hmac.new(secret.encode(), raw.encode(), hashlib.md5).hexdigest()


def build_invoice(
    *,
    merchant: str,
    secret: str,
    order_reference: str,
    amount_uah: float,
    domain: str,
    return_url: str,
    service_url: str,
) -> dict[str, Any]:
    ts = str(int(time.time()))

    # Мінімальний "товар" 1 шт, щоб пройти вимоги
    fields = [
        merchant,
        domain,
        order_reference,
        ts,
        f"{amount_uah:.2f}",
        "UAH",
        "Cart payment",
        "1",
        f"{amount_uah:.2f}",
    ]

    signature = _sign(secret, fields)

    return {
        "merchantAccount": merchant,
        "merchantDomainName": domain,
        "orderReference": order_reference,
        "orderDate": ts,
        "amount": f"{amount_uah:.2f}",
        "currency": "UAH",
        "productName[]": ["Cart payment"],
        "productCount[]": ["1"],
        "productPrice[]": [f"{amount_uah:.2f}"],
        "merchantSignature": signature,
        "returnUrl": return_url,
        "serviceUrl": service_url,
    }


def verify_callback_signature(secret: str, data: dict[str, Any]) -> bool:
    """
    WayForPay callback signature depends on fields.
    Тут робимо максимально практично:
    беремо стандартний набор полів з документації:
    merchantAccount;orderReference;amount;currency;authCode;cardPan;transactionStatus;reasonCode
    """
    try:
        fields = [
            str(data.get("merchantAccount") or ""),
            str(data.get("orderReference") or ""),
            str(data.get("amount") or ""),
            str(data.get("currency") or ""),
            str(data.get("authCode") or ""),
            str(data.get("cardPan") or ""),
            str(data.get("transactionStatus") or ""),
            str(data.get("reasonCode") or ""),
        ]
        expected = _sign(secret, fields)
        got = str(data.get("merchantSignature") or "")
        return bool(got) and hmac.compare_digest(expected, got)
    except Exception:
        return False