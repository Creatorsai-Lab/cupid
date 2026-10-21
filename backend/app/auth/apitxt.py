"""
APITxT — delivers the SMS OTP for phone login.

APITxT only sends the code we give it; it has no verify endpoint. Generating,
storing and checking the code is ours (app/auth/otp.py).

    POST {base}/api/sendOTP  authkey, mobile, otp[, template_id]
    → {"status": "success", "message": ..., "data": {"request_id", "mobile", "cost"}}

The authkey goes in the POST body, never the query string, so it stays out of
access logs.
"""

from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger("app.auth.apitxt")


class SmsSendError(Exception):
    """APITxT didn't accept the OTP (bad key, empty wallet, outage, ...)."""


async def send_otp_sms(mobile: str, code: str) -> None:
    """Send `code` to `mobile` (digits with country code). Raises SmsSendError."""
    data = {"authkey": settings.apitxt_authkey, "mobile": mobile, "otp": code}
    if settings.apitxt_sms_template_id:
        data["template_id"] = settings.apitxt_sms_template_id

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.apitxt_base_url.rstrip('/')}/api/sendOTP", data=data
            )
        body = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise SmsSendError(f"request failed: {type(exc).__name__}") from exc
    if not isinstance(body, dict):
        body = {}

    if resp.status_code != 200 or body.get("status") != "success":
        # Their message/code only (e.g. 301 insufficient balance); never the request.
        raise SmsSendError(
            f"rejected: http={resp.status_code} "
            f"code={body.get('code', body.get('status'))} msg={body.get('message')}"
        )

    logger.info(
        "[auth.otp] sms sent request_id=%s", (body.get("data") or {}).get("request_id")
    )
