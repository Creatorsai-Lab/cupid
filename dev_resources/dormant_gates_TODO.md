# Dormant Tier Gates — Wake-Up Checklist (DON'T FORGET)

_Status as of 2026-06-23: the tier policy is fully built but **NOT enforced**.
Everyone is effectively Pro because `DEFAULT_TIER_FOR_NEW_USERS = "pro"` and no
endpoint checks the policy. This file is the to-do list for the day we turn
gating on (the v1 → v2 transition)._

---

## What "dormant" means

`app/subscriptions/policy.py` defines every tier rule as a pure function
(`posts_per_day`, `can_access_earn`, …). They're correct and tested — **but
nothing calls them**. A Free user can currently do everything a Premium user
can. The gate is built; the door is propped open.

Waking a gate = adding `Depends(get_tier_context)` at the endpoint + a check,
**and** the matching locked-state in the frontend.

---

## The flip (do these together)

1. In `app/subscriptions/constants.py`, change
   `DEFAULT_TIER_FOR_NEW_USERS = "pro"` → `"free"`. New signups become Free.
2. Grandfather existing users so they don't lose access overnight: set
   `grandfathered_until = launch_date + 7 days` on their subscription (the
   resolver already keeps them on Pro until then — see `entitlement.py` Rule 1).
   Do it in bulk via a one-off script or the admin endpoint.
3. Enforce each gate below (backend = the real lock; frontend = the UX).

---

## Backend enforcement — one check per gate

Pattern at any gated endpoint:
```python
from app.subscriptions.deps import get_tier_context
from app.subscriptions.entitlement import TierContext

@router.post("/something")
async def something(ctx: TierContext = Depends(get_tier_context), ...):
    if not ctx.limits["earn_access"]:
        raise HTTPException(403, "Earn is a Creator-tier feature.")
```

| Policy / `limits` key | Rule | Enforce at (endpoint/file) |
|---|---|---|
| `posts_per_day` | Free 1 / Pro 5 / Premium ∞ per 24h | `routers/agents.py` `generate` — count today's runs per user (Redis counter keyed `posts:{user}:{YYYY-MM-DD}`), reject over limit |
| `video_posts` | Free can't create Video content type | `routers/agents.py` `generate` — if `content_type == "Video"` and not allowed → 403 |
| `earn_access` | Earn page paid-only | `earn/router.py` — gate `questions`, `profile`, `readiness` |
| `trends_view` | all tiers (always true) | no gate needed |
| `trends_refresh` | manual refresh paid-only | `routers/trends.py` `news` — if `refresh=True` and not allowed → 403 (or ignore the bypass) |
| `trends_post_tab` | "create from trend" paid-only | wherever the trend→compose action lands (future endpoint) |
| `max_social_profiles` | Free max 1 connected profile | `routers/connections.py` connect-start — count existing, reject if at cap |
| `multi_same_platform` | Premium only: 2+ of same platform | `routers/connections.py` — block second connection of same `platform` unless allowed |
| `history_retention_days` | 14 all tiers (v1) | `services/history_service.py` `list_history` — filter `created_at >= now - retention` |
| `assistant_customization` | Premium perk (not built) | future Cia settings endpoint |
| `priority` | task priority tag | tag background tasks; act on it when queue moves to Celery |

> The **backend check is the security boundary** — never trust the frontend to
> hide a feature. The frontend lock is only UX.

---

## Frontend enforcement — the locked-state UX

The frontend already has the client + types:
`entitlementApi.get()` → `Entitlement` (in `lib/api.ts`).

Plan: fetch entitlement once after login into a store (mirror `useAuthStore`),
expose `useEntitlement()`, then gate UI off `entitlement.limits.*`:

- **Create page** — disable the **Video** content-type option when
  `!limits.video_posts`; show a "Pro" lock. Show remaining posts today when
  `posts_per_day` is finite.
- **Earn page** — if `!limits.earn_access`, render a locked/upgrade screen
  instead of the coach.
- **Trends page** — hide/disable the **Refresh** button when
  `!limits.trends_refresh`; lock the **Posts** tab when `!limits.trends_post_tab`.
- **Settings → Connect** — when `max_social_profiles` reached, disable Connect +
  show the cap.
- **Global** — a small "Upgrade" affordance when `show_locked_features` is true.

Use `limits.*` for *display only*. The server re-checks on every action.

---

## Order to do it (when the time comes)

1. Fetch entitlement on the frontend + show the existing plan badge from real
   data (badge already wired in Settings; extend to a store).
2. Backend gates for the highest-value paid features first:
   **earn_access**, **posts_per_day**, **video_posts**.
3. Frontend locks matching those.
4. Connections cap + trends gates.
5. Only then flip `DEFAULT_TIER_FOR_NEW_USERS` to `free` + grandfather existing
   users. (Enforce BEFORE flipping, or Free users silently keep full access.)

---

## Gotchas

- **Flip last.** If you switch the default to Free before the gates enforce,
  every Free user keeps full access with no error — a silent revenue leak.
- **Resolve at read time.** Don't write a cron to "downgrade expired users";
  `resolve_entitlement` already does it per-request (grandfather, grace, cancel).
- **Test with the admin endpoint.** Set yourself Free and walk every gated
  surface before launch (see `dev_resources/admin_security.md`).
- **Count windows in UTC** for `posts_per_day` so the reset time is consistent.
