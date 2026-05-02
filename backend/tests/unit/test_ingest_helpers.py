"""
Unit tests for trends ingestion helpers.

═══════════════════════════════════════════════════════════════════════════
SCOPE
═══════════════════════════════════════════════════════════════════════════
This file tests PURE FUNCTIONS — no DB, no network, no async. These are
the cheapest, fastest tests in your suite. Aim for many of these.

A "pure function" means:
    - Same input always gives same output (deterministic)
    - No side effects (no DB writes, no API calls)
    - No hidden state

Examples in your codebase:
    - _url_hash(url)      → string in, string out
    - _compute_velocity() → article in, float out
    - _ensure_aware(dt)   → datetime in, datetime out

═══════════════════════════════════════════════════════════════════════════
ANATOMY OF A PYTEST TEST
═══════════════════════════════════════════════════════════════════════════
    def test_NAME():           ← function name MUST start with `test_`
        # Arrange — set up state
        x = 5

        # Act — call the thing being tested
        result = double(x)

        # Assert — check the outcome
        assert result == 10    ← `assert` is the only thing pytest needs

That's it. No special methods, no test runner config, no boilerplate.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.trends.ingest import _compute_velocity, _ensure_aware, _url_hash
from app.trends.source_client import RawArticle


# ─── _url_hash ─────────────────────────────────────────────────

class TestUrlHash:
    """Tests for the URL hashing function used as primary key."""

    def test_returns_32_char_string(self):
        """Hash must fit the VARCHAR(32) column in trending_articles."""
        h = _url_hash("https://example.com/article")
        assert isinstance(h, str)
        assert len(h) == 32

    def test_is_deterministic(self):
        """Same URL → same hash. Critical for upsert dedup logic."""
        url = "https://news.example.com/some-very-long-article-slug?utm=foo"
        assert _url_hash(url) == _url_hash(url)

    def test_different_urls_produce_different_hashes(self):
        """Two distinct URLs must not collide (except astronomically rarely)."""
        h1 = _url_hash("https://a.com/x")
        h2 = _url_hash("https://b.com/x")
        assert h1 != h2

    def test_handles_long_urls(self):
        """Real Google News URLs are 500+ chars — must still produce 32-char hash."""
        long_url = "https://news.google.com/rss/articles/" + "x" * 800
        h = _url_hash(long_url)
        assert len(h) == 32


# ─── _compute_velocity ─────────────────────────────────────────

def make_article(domain: str, hours_ago: float) -> RawArticle:
    """Helper — keeps test bodies focused on the assertion, not setup."""
    return RawArticle(
        title="test", description="", url=f"https://{domain}/x",
        image_url=None, source=domain, domain=domain,
        published_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
    )


class TestComputeVelocity:
    """Velocity score combines source authority and freshness."""

    def test_high_authority_recent_scores_near_max(self):
        """Reuters article from 1 hour ago should score near 1.0."""
        article = make_article("reuters.com", hours_ago=1)
        score = _compute_velocity(article)
        assert score > 0.9

    def test_unknown_source_old_scores_low(self):
        """Unknown source from 40 hours ago should score below 0.4."""
        article = make_article("random-blog-12345.com", hours_ago=40)
        score = _compute_velocity(article)
        assert score < 0.4

    def test_score_is_bounded_zero_to_one(self):
        """Score should never exceed 1.0 or drop below 0."""
        very_old = make_article("reuters.com", hours_ago=1000)
        very_fresh = make_article("reuters.com", hours_ago=0)
        assert 0 <= _compute_velocity(very_old) <= 1
        assert 0 <= _compute_velocity(very_fresh) <= 1

    @pytest.mark.parametrize("domain,expected_min", [
        ("reuters.com", 0.85),
        ("bbc.com", 0.85),
        ("nytimes.com", 0.85),
        ("forbes.com", 0.65),
    ])
    def test_known_authorities_score_above_threshold(self, domain, expected_min):
        """Recognized publishers with fresh articles should beat the threshold.

        Why parametrize?
            One test logic, many inputs. If the authority dict changes,
            this is the test that catches it.
        """
        article = make_article(domain, hours_ago=1)
        score = _compute_velocity(article)
        assert score >= expected_min


# ─── _ensure_aware ─────────────────────────────────────────────

class TestEnsureAware:
    """Defensive timezone handling — RSS feeds sometimes return naive datetimes."""

    def test_naive_datetime_becomes_utc(self):
        """A datetime without tzinfo should be tagged as UTC."""
        naive = datetime(2026, 1, 1, 12, 0, 0)
        aware = _ensure_aware(naive)
        assert aware.tzinfo is not None
        assert aware.utcoffset() == timedelta(0)

    def test_aware_datetime_passes_through(self):
        """Timezone-aware datetimes should not be modified."""
        original = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = _ensure_aware(original)
        assert result == original
        assert result.tzinfo == timezone.utc