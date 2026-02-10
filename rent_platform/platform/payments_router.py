# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from rent_platform.db.session import db_fetch_one, db_execute
from rent_platform.modules.telegram_shop.repo.integrations import TelegramShopIntegrationsRepo
from rent_platform.modules.telegram_shop.payments.wayforpay import (
    build_purchase_signature,
    verify_service_callback_signature,
    build_accept_response_signature,
)
from rent_platform.modules.telegram_shop.payments.ip_allowlist import parse_allowlist, is_ip_allowed


router = APIRouter(prefix="/pay", tags=["payments"])


async def _get_order(tenant_id: str, order_id: int) -> dict[str, Any] | None:
    q = """
    SELECT id, tenant_id, total_kop, currency, customer_phone
    FROM telegram_shop_orders
    WHERE tenant_id = :tid AND id = :oid
    LIMIT 1
    """
    return await db_fetch_one(q, {"tid": tenant_id, "oid": int(order_id)})


async def _get_order_items(tenant_id: str, order_id: int) -> list[dict[str, Any]]:
    q = """
    SELECT name, qty, price_kop
    FROM telegram_shop_order_items
    WHERE tenant_id = :tid AND order_id = :oid
    ORDER BY id ASC
    """
    # db_fetch_one/db_fetch_all у тебе є, але тут простий варіант:
    from rent_platform.db.session import db_fetch_all
    return await db_fetch_all(q, {"tid": tenant_id, "oid": int(order_id)}) or []


@router.get("/w4p/{tenant_id}/{order_id}", response_class=HTMLResponse)
async def w4p_pay_page(tenant_id: str, order_id: int):
    await TelegramShopIntegrationsRepo.ensure_defaults(tenant_id)

    # require enabled merchant + secret + domain
    if not await TelegramShopIntegrationsRepo.is_enabled(tenant_id, "w4p_merchant_account"):
        raise HTTPException(400, "WayForPay is not configured (merchant_account disabled)")
    if not await TelegramShopIntegrationsRepo.is_enabled(tenant_id, "w4p_secret_key"):
        raise HTTPException(400, "WayForPay is not configured (secret_key disabled)")
    if not await TelegramShopIntegrationsRepo.is_enabled(tenant_id, "w4p_domain"):
        raise HTTPException(400, "WayForPay is not configured (domain disabled)")

    merchant_account = (await TelegramShopIntegrationsRepo.get_value(tenant_id, "w4p_merchant_account")).strip()
    secret_key = (await TelegramShopIntegrationsRepo.get_value(tenant_id, "w4p_secret_key")).strip()
    domain = (await TelegramShopIntegrationsRepo.get_value(tenant_id, "w4p_domain")).strip()

    if not (merchant_account and secret_key and domain):
        raise HTTPException(400, "WayForPay values are empty")

    order = await _get_order(tenant_id, int(order_id))
    if not order:
        raise HTTPException(404, "order not found")

    items = await _get_order_items(tenant_id, int(order_id))
    if not items:
        raise HTTPException(400, "order has no items")

    order_reference = f"{tenant_id}-{int(order_id)}"
    order_date = int(time.time())
    currency = str(order.get("currency") or "UAH")
    amount = f"{int(order.get('total_kop') or 0) / 100:.2f}"

    product_names = [str(i.get("name") or "") for i in items]
    product_counts = [int(i.get("qty") or 1) for i in items]
    product_prices = [f"{int(i.get('price_kop') or 0) / 100:.2f}" for i in items]

    sig = build_purchase_signature(
        secret_key=secret_key,
        merchant_account=merchant_account,
        merchant_domain=domain,
        order_reference=order_reference,
        order_date=order_date,
        amount=amount,
        currency=currency,
        product_names=product_names,
        product_counts=product_counts,
        product_prices=product_prices,
    )

    # remember payment intent in order
    q = """
    UPDATE telegram_shop_orders
    SET payment_provider = 'wayforpay',
        payment_status = 'pending',
        payment_ref = :pref
    WHERE tenant_id = :tid AND id = :oid
    """
    await db_execute(q, {"tid": tenant_id, "oid": int(order_id), "pref": order_reference})

    # serviceUrl/callbackUrl: your backend endpoint
    service_url = f"/pay/w4p/callback/{tenant_id}"

    # HTML auto-submit
    # Note: WayForPay expects POST form to https://secure.wayforpay.com/pay 4
    inputs = []
    def _inp(name: str, value: str) -> None:
        inputs.append(f'<input type="hidden" name="{name}" value="{value}"/>')

    _inp("merchantAccount", merchant_account)
    _inp("merchantAuthType", "SimpleSignature")
    _inp("merchantDomainName", domain)
    _inp("merchantSignature", sig)
    _inp("orderReference", order_reference)
    _inp("orderDate", str(order_date))
    _inp("amount", amount)
    _inp("currency", currency)
    _inp("serviceUrl", service_url)

    # arrays
    for n in product_names:
        _inp("productName[]", n)
    for c in product_counts:
        _inp("productCount[]", str(c))
    for p in product_prices:
        _inp("productPrice[]", p)

    html = f"""
<!doctype html>
<html>
<head><meta charset="utf-8"><title>WayForPay</title></head>
<body>
<p>Redirecting to payment...</p>
<form id="w4p" method="post" action="https://secure.wayforpay.com/pay" accept-charset="utf-8">
{''.join(inputs)}
</form>
<script>document.getElementById('w4p').submit();</script>
</body>
</html>
"""
    return HTMLResponse(html)


@router.post("/w4p/callback/{tenant_id}")
async def w4p_callback(tenant_id: str, req: Request):
    await TelegramShopIntegrationsRepo.ensure_defaults(tenant_id)

    # IP allowlist optional
    allow_raw = await TelegramShopIntegrationsRepo.get_value(tenant_id, "w4p_allow_ips")
    allow_on = await TelegramShopIntegrationsRepo.is_enabled(tenant_id, "w4p_allow_ips")
    if allow_on:
        allow = parse_allowlist(allow_raw)
        remote_ip = (req.client.host if req.client else "") or ""
        if not is_ip_allowed(remote_ip, allow):
            raise HTTPException(403, "ip not allowed")

    secret_key = (await TelegramShopIntegrationsRepo.get_value(tenant_id, "w4p_secret_key")).strip()
    if not secret_key:
        raise HTTPException(400, "secret_key empty")

    payload = await req.json()

    if not verify_service_callback_signature(secret_key, payload):
        raise HTTPException(403, "bad signature")

    order_ref = str(payload.get("orderReference") or "")
    status = str(payload.get("transactionStatus") or "")
    amount = str(payload.get("amount") or "")

    # orderReference format: "{tenant_id}-{order_id}"
    if not order_ref.startswith(f"{tenant_id}-"):
        raise HTTPException(400, "bad orderReference")
    try:
        order_id = int(order_ref.split("-", 1)[1])
    except Exception:
        raise HTTPException(400, "bad order_id")

    # Approved -> paid
    paid = status.lower() == "approved"

    q = """
    UPDATE telegram_shop_orders
    SET payment_status = :ps,
        paid_ts = :pts
    WHERE tenant_id = :tid AND id = :oid
    """
    await db_execute(q, {"tid": tenant_id, "oid": int(order_id), "ps": ("paid" if paid else f"w4p:{status}"), "pts": (int(time.time()) if paid else 0)})

    # required accept response (WayForPay retries until correct response) 5
    ts = int(time.time())
    resp_status = "accept"
    resp_sig = build_accept_response_signature(secret_key, order_ref, resp_status, ts)

    return JSONResponse({"orderReference": order_ref, "status": resp_status, "time": ts, "signature": resp_sig})