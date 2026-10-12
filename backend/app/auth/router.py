"""
Auth endpoints. Sign-in is Google-only; signup and login are the same action.

    GET  /api/v1/auth/google/login     → redirect to Google consent
    GET  /api/v1/auth/google/callback  → find-or-create user, set cookie, bounce
    POST /api/v1/auth/logout           → clear cookie
    GET  /api/v1/auth/me               → current user from cookie

If the verified Google email already has an account we log in, otherwise we
create one. New accounts land on /settings (onboarding); returning users land
on /create.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.google import build_auth_url, exchange_code, fetch_userinfo
from app.auth.models import User
from app.auth.schemas import AuthResponse, UserResponse
from app.auth.service import get_user_by_email, link_google_identity
from app.auth.session import COOKIE_KEY, create_access_token, set_auth_cookie
from app.config import settings
from app.core.db import get_db
from app.core.oauth_state import (
    consume_login_state,
    generate_state_token,
    store_login_state,
)
from app.core.redis import get_redis

logger = logging.getLogger("app.auth.google")

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# ── Google sign-in ────────────────────────────────────────────


def _bounce(path: str) -> RedirectResponse:
    """Redirect to a frontend route."""
    return RedirectResponse(url=f"{settings.frontend_url}{path}")


@router.get("/google/login")
async def google_login(redis: Redis = Depends(get_redis)) -> RedirectResponse:
    """Start the flow: issue a CSRF state, then send the user to Google."""
    state = generate_state_token()
    await store_login_state(redis, state)
    return RedirectResponse(url=build_auth_url(state))


@router.get("/google/callback")
async def google_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle Google's redirect: validate, look up the user, set the cookie."""
    # User declined, or missing params, or a forged/expired state → bail safely.
    if error or not code or not state or not await consume_login_state(redis, state):
        return _bounce("/signin?error=oauth")

    try:
        tokens = await exchange_code(code)
        info = await fetch_userinfo(tokens["access_token"])
    except Exception as exc:
        logger.error("[auth.google] token/userinfo failed: %s", exc)
        return _bounce("/signin?error=oauth")

    # Only trust an email Google has verified.
    if not info.get("email_verified") or not info.get("email"):
        return _bounce("/signin?error=unverified")

    email = str(info["email"]).lower()

    # Find-or-create: this is what collapses signup and login into one action.
    user = await get_user_by_email(db, email)
    created = False

    if user is None:
        user = User(
            full_name=info.get("name") or email.split("@")[0],
            email=email,
            auth_provider="google",
            provider_account_id=info.get("sub"),
            avatar_url=info.get("picture"),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        created = True
        logger.info("[auth.google] created user %s", email)
    else:
        if not user.is_active:
            return _bounce("/signin?error=disabled")

        link_google_identity(user, info)
        await db.commit()
        await db.refresh(user)

    # Same session cookie the app already uses, then bounce to the frontend.
    dest = "/settings" if created else "/create"
    response = _bounce(f"/complete?next={dest}")
    set_auth_cookie(response, create_access_token(str(user.id)))
    return response


# ── Session ───────────────────────────────────────────────────


@router.post("/logout")
async def logout(response: Response):
    """Clear the auth cookie."""
    response.delete_cookie(key=COOKIE_KEY, path="/")
    return {"success": True, "data": None, "error": None}


@router.get("/me", response_model=AuthResponse)
async def me(user: User = Depends(get_current_user)):
    """Return the currently authenticated user."""
    return AuthResponse(data=UserResponse.model_validate(user))
