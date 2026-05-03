"""
OAuth State Tokens — CSRF protection for the OAuth flow.

═══════════════════════════════════════════════════════════════════════════
THE ATTACK WE'RE PREVENTING
═══════════════════════════════════════════════════════════════════════════
Without a state parameter, this attack works:
    1. Attacker starts the OAuth flow on their own machine, gets a Google
       auth URL pointing to Cupid's callback.
    2. Attacker tricks Victim into clicking that URL (phishing email).
    3. Victim is logged into Cupid; their browser hits Cupid's callback
       with the auth code.
    4. Cupid exchanges the code for tokens and links those tokens to
       VICTIM's Cupid account.
    5. Now the ATTACKER's YouTube channel is connected to the VICTIM's
       Cupid account. Attacker can read victim's posting patterns,
       see private analytics, etc.

Defense: when Cupid generates the auth URL, it includes a random `state`
parameter and stores that state with the user_id. Google passes state
back unchanged. Cupid verifies the returned state was issued for the
currently-logged-in user. Mismatch → reject the callback.

═══════════════════════════════════════════════════════════════════════════
WHERE WE STORE STATE
═══════════════════════════════════════════════════════════════════════════
We use Redis with a short TTL (10 minutes — OAuth flows take seconds,
so 10min is generous). After the callback, the state is consumed and
deleted. Single-use, time-limited, server-side stored.

Why not a cookie? Cookies can be tampered with by a clever attacker
in a same-site scenario. Server-side state is the canonical defense.

═══════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import secrets
from typing import Final

from redis.asyncio import Redis

# 10 minutes — OAuth dance takes seconds, this is plenty of headroom
STATE_TTL_SECONDS: Final[int] = 600

# Redis key prefix for namespacing
KEY_PREFIX: Final[str] = "oauth:state:"


def generate_state_token() -> str:
    """
    Generate a cryptographically secure random state token.

    secrets.token_urlsafe is the standard for one-shot security tokens.
    32 bytes → 43 url-safe chars, plenty of entropy (~256 bits).
    """
    return secrets.token_urlsafe(32)


async def store_state(redis: Redis, state: str, user_id: str, platform: str) -> None:
    """
    Persist the state with the user_id so we can validate it on callback.

    Stores: oauth:state:{state} → "{user_id}:{platform}" with 10min TTL

    Why include platform in the value: in case a user happens to start
    OAuth flows for two platforms simultaneously, we know which platform
    each state belongs to and can route the callback correctly.
    """
    key = f"{KEY_PREFIX}{state}"
    value = f"{user_id}:{platform}"
    await redis.set(key, value, ex=STATE_TTL_SECONDS)


async def consume_state(
    redis: Redis,
    state: str,
    expected_platform: str,
) -> str | None:
    """
    Validate and CONSUME a state token. Returns the user_id if valid.

    Single-use — we DELETE the state after reading. This prevents replay
    attacks where someone sniffs the callback URL and tries to use it
    again.

    Returns None if:
        - state doesn't exist (expired, never issued, already consumed)
        - platform mismatch
    """
    key = f"{KEY_PREFIX}{state}"

    # Atomic GETDEL — read and delete in one operation
    raw = await redis.getdel(key)

    if not raw:
        return None

    # raw is "user_id:platform" — split and validate
    if ":" not in raw:
        return None

    user_id, platform = raw.split(":", 1)

    if platform != expected_platform:
        # Someone is reusing a state issued for a different platform — reject
        return None

    return user_id