"""
Authentication router — HTTP endpoints for register, login, logout, and current user.

Endpoints:
    POST /api/v1/auth/register  → create account + set cookie
    POST /api/v1/auth/login     → verify credentials + set cookie
    POST /api/v1/auth/logout    → clear cookie
    GET  /api/v1/auth/me        → return current user from cookie
"""

from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import create_access_token, decode_access_token
from app.models.user import User
from app.schemas.auth import (
    UserCreate,
    LoginRequest,          
    UserResponse,
    AuthResponse,
)
from app.services.auth import authenticate_user, create_user, get_user_by_email

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Cookie configuration
COOKIE_KEY = "cupid_access_token"
COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 days in seconds


def _set_auth_cookie(response: Response, token: str) -> None:
    """
    Set the JWT as an HTTP-only cookie.
    
    httponly=True   → JS can't read it (XSS protection)
    secure=False    → allows HTTP in dev. Set True in production (HTTPS only)
    samesite="lax"  → cookie sent on same-site requests + top-level navigations
                      "strict" would break OAuth redirects
    """
    response.set_cookie(
        key=COOKIE_KEY,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=False,        # TODO: set True in production
        samesite="lax",
        path="/",
    )


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency — extracts and verifies the JWT from the cookie.
    
    Use this on any endpoint that requires authentication:
        @router.get("/something")
        async def handler(user: User = Depends(get_current_user)):
            ...
    """
    token = request.cookies.get(COOKIE_KEY)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    from sqlalchemy import select
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user


# ── Endpoints ─────────────────────────────────────────────────

@router.post("/register", response_model=AuthResponse)
async def register(
    body: UserCreate,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Create a new user account."""
    # Check if email already taken
    existing = await get_user_by_email(db, body.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    
    user = await create_user(db, body.full_name, body.email, body.password)
    token = create_access_token(str(user.id))
    _set_auth_cookie(response, token)
    
    return AuthResponse(data=UserResponse.model_validate(user))


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate and receive session cookie."""
    user = await authenticate_user(db, body.email, body.password)
    if not user:
        # Generic message — don't reveal whether email exists
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    token = create_access_token(str(user.id))
    _set_auth_cookie(response, token)
    
    return AuthResponse(data=UserResponse.model_validate(user))


@router.post("/logout")
async def logout(response: Response):
    """Clear the auth cookie."""
    response.delete_cookie(key=COOKIE_KEY, path="/")
    return {"success": True, "data": None, "error": None}


@router.get("/me", response_model=AuthResponse)
async def me(user: User = Depends(get_current_user)):
    """Return the currently authenticated user."""
    return AuthResponse(data=UserResponse.model_validate(user))
