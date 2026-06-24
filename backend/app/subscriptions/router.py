"""
app/subscriptions/router.py
═══════════════════════════════════════════════════════════════════════════

Two endpoints:

  GET  /api/v1/entitlement                       — the frontend reads this
  POST /api/v1/admin/users/{user_id}/tier        — manual override (v1) /
                                                   audit point (v2)

The /entitlement endpoint is the SINGLE source the UI consumes for
tier-aware rendering. Fetch on login, re-fetch after billing actions.

The admin endpoint is the manual control surface during v1 (and the audit
point during v2 — Stripe webhooks call set_user_tier directly, not via
HTTP, but admin actions still flow through this endpoint for visibility).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.security import require_admin
from app.core.db import get_db
from app.models.user import User
from app.subscriptions import service
from app.subscriptions.deps import get_tier_context
from app.subscriptions.entitlement import TierContext
from app.subscriptions.schemas import (
    AdminSetTierRequest,
    EntitlementResponse,
)

router = APIRouter(prefix="/api/v1", tags=["subscriptions"])


# ─────────────────────────────────────────────────────────────────────────
#  GET /entitlement — what the user can do, right now
# ─────────────────────────────────────────────────────────────────────────


@router.get("/entitlement", response_model=EntitlementResponse)
async def get_entitlement(
    ctx: TierContext = Depends(get_tier_context),
) -> EntitlementResponse:
    """
    The frontend's source of truth for tier-aware UI. Always honest:
    returns the actual effective tier, the actual display name, the
    actual limits — no launch-window obfuscation.
    """
    return EntitlementResponse(
        tier=ctx.tier,
        display_name=ctx.display_name,
        tier_rank=ctx.tier_rank,
        status=ctx.status,
        payment_warning=ctx.payment_warning,
        show_locked_features=ctx.show_locked_features,
        cancel_at_period_end=ctx.cancel_at_period_end,
        period_end=ctx.period_end,
        grandfathered_until=ctx.grandfathered_until,
        limits=ctx.limits,
    )


# ─────────────────────────────────────────────────────────────────────────
#  POST /admin/users/{user_id}/tier — manual tier control
# ─────────────────────────────────────────────────────────────────────────
# Gated by require_admin (is_admin flag → 404 to everyone else) and hidden
# from the public OpenAPI docs (include_in_schema=False). It's also the
# AUDITED tier-write path — every call records an audit_log row.


@router.post(
    "/admin/users/{user_id}/tier",
    response_model=EntitlementResponse,
    include_in_schema=False,
)
async def admin_set_tier(
    user_id: uuid.UUID,
    payload: AdminSetTierRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> EntitlementResponse:
    """
    Manually set a user's tier. Used to:
      - Promote/demote support cases during v1
      - Test the locked-feature UI by setting yourself to Free
      - Grandfather users during the v1→v2 transition

    Calls into the same service.set_user_tier that Stripe webhooks will
    call in v2 — so there's no separate "admin path" to keep in sync.
    """
    try:
        sub = await service.set_user_tier(
            session=db,
            user_id=user_id,
            tier=payload.tier,
            grandfathered_until=payload.grandfathered_until,
            reason=f"admin:{payload.reason}",
            actor_id=admin.id,
            actor_email=admin.email,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )

    # Return the freshly-resolved entitlement so the caller sees the result.
    from app.subscriptions.entitlement import resolve_entitlement

    ctx = resolve_entitlement(sub)
    return EntitlementResponse(
        tier=ctx.tier,
        display_name=ctx.display_name,
        tier_rank=ctx.tier_rank,
        status=ctx.status,
        payment_warning=ctx.payment_warning,
        show_locked_features=ctx.show_locked_features,
        cancel_at_period_end=ctx.cancel_at_period_end,
        period_end=ctx.period_end,
        grandfathered_until=ctx.grandfathered_until,
        limits=ctx.limits,
    )
