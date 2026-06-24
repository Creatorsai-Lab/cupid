"""
app/subscriptions/schemas.py
═══════════════════════════════════════════════════════════════════════════

Pydantic contracts for the subscription endpoints. The frontend depends on
the exact shape of EntitlementResponse — keep its keys stable.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.subscriptions.constants import is_valid_tier

# ─────────────────────────────────────────────────────────────────────────
#  GET /api/v1/entitlement
# ─────────────────────────────────────────────────────────────────────────


class EntitlementResponse(BaseModel):
    """
    What the frontend fetches once per session (and re-fetches after any
    billing action). Every key here is consumed by the UI.
    """

    tier: str  # "free" | "pro" | "premium" — internal id
    display_name: str  # "Hustler" | "Creator" | "Influencer"
    tier_rank: int  # 0/1/2 for ordering checks
    status: str  # mirrored Stripe status
    payment_warning: bool  # show "payment failed" banner?
    show_locked_features: bool  # render locked overlays on premium features?
    cancel_at_period_end: bool  # show "your plan ends on X" message?
    period_end: datetime | None = None
    grandfathered_until: datetime | None = None
    limits: dict  # the policy_summary for this tier


# ─────────────────────────────────────────────────────────────────────────
#  POST /api/v1/admin/users/{user_id}/tier
# ─────────────────────────────────────────────────────────────────────────


class AdminSetTierRequest(BaseModel):
    """
    Admin/manual tier change. Used during v1 for support and for testing the
    locked-feature UI without needing Stripe. In v2 this becomes one of
    several callers of service.set_user_tier (alongside Stripe webhooks).
    """

    tier: str = Field(..., description="One of: free, pro, premium")
    grandfathered_until: datetime | None = Field(
        None, description="Optional: keep user on this tier until this date"
    )
    reason: str = Field("admin", description="Free-text reason for the audit log")

    @field_validator("tier")
    @classmethod
    def _validate_tier(cls, v: str) -> str:
        if not is_valid_tier(v):
            raise ValueError(f"Invalid tier: {v!r}. Must be free, pro, or premium.")
        return v
