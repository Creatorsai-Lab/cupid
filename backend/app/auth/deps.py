"""Auth dependencies for routes: the signed-in user from the session cookie."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select

from app.auth.models import User
from app.auth.session import COOKIE_KEY, decode_access_token
from app.core.db import DbSession


async def get_current_user(request: Request, db: DbSession) -> User:
    """
    FastAPI dependency — extracts and verifies the JWT from the cookie.

    Use it on any endpoint that requires authentication:
        @router.get("/something")
        async def handler(user: CurrentUser): ...
    """
    token = request.cookies.get(COOKIE_KEY)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account is disabled")

    return user


# Route parameter shortcut: `user: CurrentUser` instead of `Depends(get_current_user)`.
CurrentUser = Annotated[User, Depends(get_current_user)]
