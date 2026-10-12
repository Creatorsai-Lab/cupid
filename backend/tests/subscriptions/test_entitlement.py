"""Entitlement rules: what a subscription row actually grants, at a given moment.

resolve_entitlement() is pure (time is passed in), so these are plain unit tests.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.subscriptions.constants import (
    STATUS_ACTIVE,
    STATUS_CANCELED,
    STATUS_INCOMPLETE,
    STATUS_PAST_DUE,
    TIER_FREE,
    TIER_PREMIUM,
    TIER_PRO,
)
from app.subscriptions.entitlement import resolve_entitlement
from app.subscriptions.policy import policy_summary
from tests.factories import make_subscription

NOW = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(days=3)
EARLIER = NOW - timedelta(days=3)


def tier_of(**fields) -> str:
    return resolve_entitlement(make_subscription(**fields), now=NOW).tier


@pytest.mark.parametrize("tier", [TIER_FREE, TIER_PRO, TIER_PREMIUM])
def test_active_subscription_keeps_its_tier(tier):
    assert tier_of(tier=tier, status=STATUS_ACTIVE) == tier


def test_past_due_keeps_access_but_warns():
    ctx = resolve_entitlement(
        make_subscription(tier=TIER_PRO, status=STATUS_PAST_DUE), now=NOW
    )
    assert ctx.tier == TIER_PRO
    assert ctx.payment_warning is True


def test_canceled_keeps_tier_until_paid_period_ends():
    assert (
        tier_of(tier=TIER_PRO, status=STATUS_CANCELED, current_period_end=LATER)
        == TIER_PRO
    )


@pytest.mark.parametrize("period_end", [EARLIER, None])
def test_canceled_drops_to_free_after_period(period_end):
    assert (
        tier_of(tier=TIER_PRO, status=STATUS_CANCELED, current_period_end=period_end)
        == TIER_FREE
    )


def test_incomplete_signup_gets_free():
    assert tier_of(tier=TIER_PREMIUM, status=STATUS_INCOMPLETE) == TIER_FREE


def test_grandfather_window_lifts_free_to_pro():
    assert tier_of(tier=TIER_FREE, grandfathered_until=LATER) == TIER_PRO


def test_grandfather_never_downgrades_premium():
    assert tier_of(tier=TIER_PREMIUM, grandfathered_until=LATER) == TIER_PREMIUM


def test_expired_grandfather_window_does_nothing():
    assert tier_of(tier=TIER_FREE, grandfathered_until=EARLIER) == TIER_FREE


def test_limits_follow_the_effective_tier_not_the_billed_one():
    ctx = resolve_entitlement(
        make_subscription(tier=TIER_PREMIUM, status=STATUS_INCOMPLETE), now=NOW
    )
    assert ctx.limits == policy_summary(TIER_FREE)
    assert ctx.limits["posts_per_day"] == 1


@pytest.mark.parametrize(
    ("tier", "posts", "video", "earn", "profiles", "show_locks"),
    [
        (TIER_FREE, 1, False, False, 1, True),
        (TIER_PRO, 5, True, True, None, True),
        (TIER_PREMIUM, 999_999, True, True, None, False),
    ],
)
def test_tier_capabilities(tier, posts, video, earn, profiles, show_locks):
    ctx = resolve_entitlement(make_subscription(tier=tier), now=NOW)
    assert ctx.limits["posts_per_day"] == posts
    assert ctx.limits["video_posts"] is video
    assert ctx.limits["earn_access"] is earn
    assert ctx.limits["max_social_profiles"] == profiles
    assert ctx.show_locked_features is show_locks
