"""
Authentication service — business logic for user registration and login.

This layer sits between the router (HTTP) and the database (models).
It contains the actual logic: create user, check password, etc.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.user import User


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Look up a user by email. Returns None if not found."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, name: str, email: str, password: str) -> User:
    """
    Register a new user.
    
    Steps:
    1. Hash the password (never store plain text)
    2. Create User object
    3. Add to session and commit (write to database)
    4. Refresh to load server-generated fields (id, created_at)
    """
    user = User(
        full_name=name,
        email=email,
        hashed_password=hash_password(password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)    # reload from DB to get id + created_at
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    """
    Verify login credentials.
    
    Returns the User if credentials are valid, None otherwise.
    Note: we return None for BOTH "user not found" and "wrong password".
    This prevents attackers from discovering which emails are registered
    (a technique called "user enumeration").
    """
    user = await get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
