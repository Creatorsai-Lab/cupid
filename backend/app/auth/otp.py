"""
Phone OTP — issue and check one-time login codes.

APITxT only delivers the SMS; the code lives here, in Redis, as an HMAC (never
the plain code), keyed by phone:

    otp:code:{phone}      hash {h, tries}  TTL 5 min — the live code
    otp:cooldown:{phone}  "1"              TTL 60 s  — one send per minute
    otp:sent:{phone}      counter          TTL 1 h   — sends per phone per hour
    otp:ip:{ip}           counter          TTL 1 h   — sends per IP per hour

A new send replaces the old code. A code dies after MAX_ATTEMPTS wrong tries,
on success (single use), or at its TTL.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from typing import Final

from redis.asyncio import Redis

from app.auth.apitxt import SmsSendError, send_otp_sms
from app.config import settings
from app.core.errors import AppError, ServiceUnavailableError

CODE_LENGTH: Final[int] = 6
CODE_TTL_SECONDS: Final[int] = 300
RESEND_COOLDOWN_SECONDS: Final[int] = 60
MAX_ATTEMPTS: Final[int] = 5
SENDS_PER_PHONE_PER_HOUR: Final[int] = 5
SENDS_PER_IP_PER_HOUR: Final[int] = 20
DEFAULT_COUNTRY_CODE: Final[str] = "91"

CODE_KEY: Final[str] = "otp:code:"
COOLDOWN_KEY: Final[str] = "otp:cooldown:"
PHONE_COUNT_KEY: Final[str] = "otp:sent:"
IP_COUNT_KEY: Final[str] = "otp:ip:"


class InvalidPhoneError(AppError):
    status, code = 422, "invalid_phone"


class InvalidCodeError(AppError):
    status, code = 400, "invalid_code"


class RateLimitedError(AppError):
    status, code = 429, "rate_limited"


class SmsDeliveryError(AppError):
    status, code = 502, "sms_failed"


def normalize_phone(raw: str) -> str:
    """'+91 99999-99999' / '9999999999' → '919999999999'. Raises InvalidPhoneError."""
    digits = re.sub(r"[\s\-()]", "", raw).removeprefix("+")
    if not digits.isdigit():
        raise InvalidPhoneError("Phone number must contain digits only.")
    if len(digits) == 10:
        digits = DEFAULT_COUNTRY_CODE + digits
    if not 11 <= len(digits) <= 15 or digits.startswith("0"):
        raise InvalidPhoneError("Enter a valid mobile number with country code.")
    return digits


def _hash(phone: str, code: str) -> str:
    # Keyed with the app secret so a Redis dump can't be brute-forced offline.
    return hmac.new(
        settings.secret_key.encode(), f"{phone}:{code}".encode(), hashlib.sha256
    ).hexdigest()


async def _bump(redis: Redis, key: str, window: int) -> int:
    """Increment a fixed-window counter; the first hit starts the window."""
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window)
    return count


async def send_code(redis: Redis, phone: str, ip: str) -> None:
    """Generate a code for `phone`, store its hash, and SMS it."""
    if not settings.apitxt_authkey:
        raise ServiceUnavailableError("Phone login is not configured.")

    if await _bump(redis, f"{IP_COUNT_KEY}{ip}", 3600) > SENDS_PER_IP_PER_HOUR:
        raise RateLimitedError("Too many codes requested. Try again later.")

    # SET NX: only one send per phone per cooldown, even under concurrent requests.
    if not await redis.set(
        f"{COOLDOWN_KEY}{phone}", "1", nx=True, ex=RESEND_COOLDOWN_SECONDS
    ):
        wait = await redis.ttl(f"{COOLDOWN_KEY}{phone}")
        raise RateLimitedError(f"Wait {max(wait, 1)}s before requesting a new code.")

    if await _bump(redis, f"{PHONE_COUNT_KEY}{phone}", 3600) > SENDS_PER_PHONE_PER_HOUR:
        raise RateLimitedError("Too many codes for this number. Try again later.")

    code = f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"
    key = f"{CODE_KEY}{phone}"
    async with redis.pipeline(transaction=True) as pipe:
        pipe.delete(key)
        pipe.hset(key, mapping={"h": _hash(phone, code), "tries": 0})
        pipe.expire(key, CODE_TTL_SECONDS)
        await pipe.execute()

    try:
        await send_otp_sms(phone, code)
    except SmsSendError as exc:
        # Nothing was delivered: drop the code and let the user retry at once.
        await redis.delete(key, f"{COOLDOWN_KEY}{phone}")
        raise SmsDeliveryError("Couldn't send the code. Try again shortly.") from exc


async def verify_code(redis: Redis, phone: str, code: str) -> None:
    """Check `code` for `phone` and consume it. Raises InvalidCodeError."""
    key = f"{CODE_KEY}{phone}"
    # Count the try before comparing, so parallel guesses can't skip the limit.
    async with redis.pipeline(transaction=True) as pipe:
        pipe.hincrby(key, "tries", 1)
        pipe.hget(key, "h")
        tries, stored = await pipe.execute()

    if not stored:
        # No live code; HINCRBY just created a stray key, so remove it.
        await redis.delete(key)
        raise InvalidCodeError("Code expired or not requested. Request a new one.")

    if tries > MAX_ATTEMPTS:
        await redis.delete(key)
        raise InvalidCodeError("Too many wrong attempts. Request a new code.")

    if not hmac.compare_digest(stored, _hash(phone, code)):
        raise InvalidCodeError("Incorrect code.")

    # Single use: whoever deletes the key wins; a concurrent duplicate loses.
    if not await redis.delete(key):
        raise InvalidCodeError("Code expired or not requested. Request a new one.")
