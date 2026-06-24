"""
app/admin/security.py
═══════════════════════════════════════════════════════════════════════════

Two independent admin defenses live here:

  1. require_admin  — the gate for the PROGRAMMATIC admin API (e.g. the tier
     endpoint). Reads the durable `users.is_admin` flag and returns **404**
     (not 403) to everyone else, so a scanner can't even tell the route exists.

  2. AdminAuth      — the credential wall for the SQLAdmin DASHBOARD. A
     separate username/password (from env), unrelated to app login. The
     dashboard is a different surface, so it gets a different lock.

  3. bootstrap_admins — promotes the env allowlist (settings.admin_emails) to
     is_admin=True at startup. This is how you "designate" yourself admin
     without hand-editing the database, and it survives the future move to
     social login (it keys on the verified email).
"""

from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException, status
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.config import settings
from app.models.user import User
from app.routers.auth import get_current_user

# ─────────────────────────────────────────────────────────────────────────
#  1. Gate for the admin API (404 to non-admins)
# ─────────────────────────────────────────────────────────────────────────


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Allow only is_admin users. Non-admins get 404 — not 403 — so the endpoint
    is indistinguishable from "doesn't exist". The real security is this flag
    check; obscuring the URL is only a thin extra layer on top.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return current_user


# ─────────────────────────────────────────────────────────────────────────
#  2. Startup bootstrap — env allowlist → is_admin column
# ─────────────────────────────────────────────────────────────────────────


async def bootstrap_admins(session: AsyncSession) -> int:
    """
    Set is_admin=True for any user whose email is in settings.admin_emails.
    Idempotent; run once at startup. Returns how many users were newly promoted.
    """
    emails = settings.admin_emails
    if not emails:
        return 0

    result = await session.execute(
        select(User).where(func.lower(User.email).in_(emails))
    )
    promoted = 0
    for user in result.scalars().all():
        if not user.is_admin:
            user.is_admin = True
            promoted += 1
    if promoted:
        await session.commit()
    return promoted


# ─────────────────────────────────────────────────────────────────────────
#  3. SQLAdmin dashboard credential wall
# ─────────────────────────────────────────────────────────────────────────


class AdminAuth(AuthenticationBackend):
    """
    Username/password gate for the SQLAdmin dashboard, checked against
    settings.admin_panel_user / admin_panel_password. Uses constant-time
    comparison to avoid leaking the credential via timing.
    """

    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = str(form.get("username") or "")
        password = str(form.get("password") or "")

        expected_user = settings.admin_panel_user
        expected_pass = settings.admin_panel_password
        ok = bool(
            expected_user
            and expected_pass
            and secrets.compare_digest(username, expected_user)
            and secrets.compare_digest(password, expected_pass)
        )
        if ok:
            request.session.update({"admin_ok": True})
        return ok

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return bool(request.session.get("admin_ok"))
