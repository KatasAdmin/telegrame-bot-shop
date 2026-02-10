# -*- coding: utf-8 -*-
from __future__ import annotations

import hmac
import hashlib
from typing import Any


def _hmac_md5(secret_key: str, s: str) -> str:
    return hmac.new(secret_key.encode("utf-8"), s.encode("utf-8"), hashlib.md5).hexdigest()


def build_purchase_signature(
    *,
    secret_key: str,
    merchant_account: str,
    merchant_domain: str,
    order_reference: str,
    order_date: int,
    amount: str,
    currency: str,
    product_names: list[str],
    product_counts: list[int],
    product_prices: list[str],
) -> str:
    """
    Request signature for /pay form:
    merchantAccount;merchantDomainName;orderReference;orderDate;amount;currency;
    productName...;productCount...;productPrice... 1
    """
    parts: list[str] = [
        merchant_account,
        merchant_domain,
        order_reference,
        str(int(order_date)),
        str(amount),
        str(currency),
    ]
    parts += [str(x) for x in product_names]
    parts += [str(int(x)) for x in product_counts]
    parts += [str(x) for x in product_prices]
    base = ";".join(parts)
    return _hmac_md5(secret_key, base)


def verify_service_callback_signature(secret_key: str, payload: dict[str, Any]) -> bool:
    """
    Callback signature for serviceUrl:
    merchantAccount;orderReference;amount;currency;authCode;cardPan;transactionStatus;reasonCode 2
    """
    need = ["merchantAccount", "orderReference", "amount", "currency", "authCode", "cardPan", "transactionStatus", "reasonCode"]
    if any(k not in payload for k in need):
        return False
    base = ";".join(str(payload.get(k, "")) for k in need)
    sig = _hmac_md5(secret_key, base)
    got = str(payload.get("merchantSignature") or "")
    return sig.lower() == got.lower()


def build_accept_response_signature(secret_key: str, order_reference: str, status: str, ts: int) -> str:
    """
    Merchant response signature:
    orderReference;status;time 3
    """
    base = ";".join([str(order_reference), str(status), str(int(ts))])
    return _hmac_md5(secret_key, base)