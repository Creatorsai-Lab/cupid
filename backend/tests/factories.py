"""Model instances with sensible defaults; override any field by keyword.

user = make_user(is_active=False)
await save(db_session, user, make_history(user, prompt="..."))
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.history.models import CreationHistory
from app.subscriptions.constants import STATUS_ACTIVE, TIER_PRO
from app.subscriptions.models import Subscription


def make_user(**fields) -> User:
    tag = uuid.uuid4().hex[:8]
    defaults = {
        "id": uuid.uuid4(),
        "full_name": f"Test User {tag}",
        "email": f"user-{tag}@example.com",
        "auth_provider": "google",
        "is_active": True,
    }
    return User(**(defaults | fields))


def make_history(user: User, **fields) -> CreationHistory:
    defaults = {
        "id": uuid.uuid4(),
        "user_id": user.id,
        "prompt": "Write a post about testing",
        "target_platform": "LinkedIn",
        "tone": "Formal",
        "variants": [
            {"angle": "", "platform": "LinkedIn", "content": "Draft", "char_count": 5}
        ],
    }
    return CreationHistory(**(defaults | fields))


def make_subscription(**fields) -> Subscription:
    """Unsaved by default: entitlement rules are pure functions of this row."""
    defaults = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "tier": TIER_PRO,
        "status": STATUS_ACTIVE,
        "cancel_at_period_end": False,
        "current_period_end": None,
        "grandfathered_until": None,
    }
    return Subscription(**(defaults | fields))


async def save(session: AsyncSession, *objects: object) -> None:
    """Add objects and flush, so they get database defaults and are queryable."""
    session.add_all(objects)
    await session.flush()
