"""
app/subscriptions/deps.py dependencies
═══════════════════════════════════════════════════════════════════════════

The FastAPI dependency that turns "this request's authenticated user" into
"this request's tier context" — the security boundary of the whole system.

THIS IS THE ANTI-INJECTION DEFENSE
──────────────────────────────────
The frontend never sends tier in the request body. It can't lie because it
isn't asked. Instead, every endpoint that cares about tier depends on
`get_tier_context`, which:

  1. Resolves the user from the auth cookie/token (existing get_current_user)
  2. Looks up that user's subscription row server-side
  3. Runs the entitlement resolver
  4. Returns the immutable TierContext

Any tier-aware code path reads from this context. Tier is impossible to forge
because tier never traveled in user-controlled data — it was computed from
server-trusted authentication state and a server-trusted database row.

USAGE (in any router that needs tier-awareness):

    @router.post("/some-action")
    async def some_action(
        ctx: TierContext = Depends(get_tier_context),
        ...
    ):
        if not ctx.limits["earn_access"]:
            raise HTTPException(403, "Earn is a Creator-tier feature.")
        ...
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

# Shared infra — referenced, not modified.
from app.core.db import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.subscriptions.entitlement import TierContext, resolve_entitlement
from app.subscriptions.service import ensure_subscription


async def get_tier_context(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TierContext:
    """
    Resolve the request's tier context. Cheap (one indexed lookup +
    one pure-function call); cached implicitly by FastAPI within a single
    request, so multiple deps in one endpoint share the lookup.
    """
    sub = await ensure_subscription(db, current_user.id)
    return resolve_entitlement(sub)
