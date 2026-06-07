"""
app/earn/signals.py
═══════════════════════════════════════════════════════════════════════════

The ONE place the Earn feature reads a creator's audience numbers. Everything
downstream (tiers, readiness) consumes the AudienceSignals this produces.

WHY THIS IS ISOLATED IN ITS OWN FILE
────────────────────────────────────
Two reasons, both deliberate:

  1. It's the only impure edge of the eligibility engine. By confining all
     I/O to signals.py, the actual decision logic (tiers.py, readiness.py)
     stays pure and testable. This is the "push data-gathering to the edges"
     discipline.

  2. It's the only file coupled to your existing data shape. The brief says
     app/earn/ must not edit other modules — so rather than importing the
     insights service, signals.py does its OWN read. If your insights schema
     ever changes, THIS is the single file to update, and nothing else in the
     feature cares.

DEFENSIVE BY CONTRACT
─────────────────────
This function must NEVER raise. If the tables/columns differ from what's
assumed, or nothing is connected yet, it returns AudienceSignals.empty() and
the feature degrades gracefully to a low-confidence "connect more to get
sharper advice" state. A monetization page that 500s because a column was
renamed would be far worse than one that honestly says "not enough data yet".

⚠️  ADAPT THE QUERY BELOW TO YOUR REAL SCHEMA
─────────────────────────────────────────────
The SQL is written against the most likely shape of your insights data, but
you know the exact table/column names. Search for "ADJUST" and point it at
your real columns. Until you do, it will safely return empty signals.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.earn.tiers import AudienceSignals

logger = logging.getLogger("app.earn.signals")


async def gather_signals(session: AsyncSession, user_id: str) -> AudienceSignals:
    """
    Read and sum the creator's public audience metrics across all connected
    platforms. Returns AudienceSignals.empty() on any problem — never raises.
    """
    try:
        return await _query_signals(session, user_id)
    except Exception as exc:  # noqa: BLE001 — intentional catch-all at the I/O edge
        # Log loudly for us, fail soft for the user.
        logger.warning(
            "[earn.signals] could not gather signals for user=%s (%s) — "
            "returning empty; check the query against your insights schema",
            user_id,
            str(exc)[:160],
        )
        return AudienceSignals.empty()


async def _query_signals(session: AsyncSession, user_id: str) -> AudienceSignals:
    """
    The actual read. Isolated so gather_signals() can wrap it in the safety net.

    ASSUMED SCHEMA (ADJUST to your real one):
      • A table of social connections, one row per connected platform per user.
      • A table of per-platform metric snapshots with follower/view/post counts,
        where we want the LATEST snapshot per platform.

    The query below takes the most recent snapshot per connected platform and
    sums the three numbers we need. If your insights store keeps a single
    "current" row per connection instead of historical snapshots, the LATEST
    logic collapses to a simple read — either way the SUM is what we want.
    """
    # ── ADJUST: table/column names to match your insights schema ──────────
    #
    # Expected columns from the snapshot read:
    #   platform_count : number of distinct connected platforms
    #   followers      : SUM of latest follower/subscriber counts
    #   monthly_views  : SUM of latest monthly/period view counts
    #   posts          : SUM of latest post/video counts
    #
    # This uses DISTINCT ON (Postgres) to grab the newest snapshot per
    # connection before summing. Replace `insights_snapshots`, `social_connections`,
    # and the column names with yours.
    sql = text(
        """
        WITH latest AS (
            SELECT DISTINCT ON (s.connection_id)
                   s.connection_id,
                   COALESCE(s.subscriber_count, s.follower_count, 0) AS followers,
                   COALESCE(s.view_count, 0)                          AS views,
                   COALESCE(s.video_count, s.post_count, 0)           AS posts
            FROM insights_snapshots s
            JOIN social_connections c ON c.id = s.connection_id
            WHERE c.user_id = :uid
            ORDER BY s.connection_id, s.created_at DESC
        )
        SELECT
            COUNT(*)                       AS platform_count,
            COALESCE(SUM(followers), 0)    AS followers,
            COALESCE(SUM(views), 0)        AS monthly_views,
            COALESCE(SUM(posts), 0)        AS posts
        FROM latest
        """
    )

    result = await session.execute(sql, {"uid": user_id})
    row = result.first()

    if row is None or (row.platform_count or 0) == 0:
        return AudienceSignals.empty()

    return AudienceSignals(
        total_followers=int(row.followers or 0),
        monthly_views=int(row.monthly_views or 0),
        total_posts=int(row.posts or 0),
        connected_platforms=int(row.platform_count or 0),
        has_data=True,
    )
