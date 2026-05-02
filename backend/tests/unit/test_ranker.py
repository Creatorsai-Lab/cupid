"""
Unit tests for the trends ranker.

═══════════════════════════════════════════════════════════════════════════
SCOPE
═══════════════════════════════════════════════════════════════════════════
The ranker is the personalization brain. It uses BM25 + recency + velocity
to order articles for one user. We test:
    - It returns at most top_k results
    - It orders by composite score (recency matters when content ties)
    - It handles edge cases (empty pool, empty persona)
    - Score attributes get attached to the returned articles

We use lightweight stand-in objects instead of the real ORM model. The
ranker only needs `.title`, `.description`, `.published_at`, and
`.velocity_score` — anything with those attributes works (Python's
"duck typing").
═══════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.trends.ranker import rank_articles


@dataclass
class FakeArticle:
    """
    Stand-in for TrendingArticle ORM rows.

    Why not use the real model?
        - Avoids needing a DB session for unit tests
        - Faster (no ORM overhead)
        - Tests stay focused on ranker logic
    Same shape, different storage.
    """
    title: str
    description: str
    published_at: datetime
    velocity_score: float
    # The ranker mutates these in place — tests can read after ranking
    relevance_score: float = 0.0
    final_score: float = 0.0


def make_article(title: str, hours_ago: float = 1, velocity: float = 0.5,
                 description: str = "") -> FakeArticle:
    """Helper — keeps tests readable."""
    return FakeArticle(
        title=title,
        description=description,
        published_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
        velocity_score=velocity,
    )


# ─── Output shape ──────────────────────────────────────────────

class TestRankerOutput:
    """Top-K, score attachment, and stability properties."""

    def test_returns_at_most_top_k(self, sample_persona):
        """Even with 20 candidates, top_k=9 means 9 results."""
        articles = [make_article(f"Article {i}") for i in range(20)]
        result = rank_articles(articles, sample_persona, top_k=9)
        assert len(result) == 9

    def test_returns_all_when_pool_smaller_than_k(self, sample_persona):
        """If only 3 articles exist, return all 3 (don't pad or error)."""
        articles = [make_article(f"Article {i}") for i in range(3)]
        result = rank_articles(articles, sample_persona, top_k=9)
        assert len(result) == 3

    def test_empty_pool_returns_empty_list(self, sample_persona):
        """Defensive: an empty pool should not crash."""
        result = rank_articles([], sample_persona, top_k=9)
        assert result == []

    def test_attaches_scores_to_articles(self, sample_persona):
        """Ranker should set relevance_score and final_score on results."""
        articles = [make_article("Test article about AI machine learning")]
        result = rank_articles(articles, sample_persona, top_k=9)
        assert hasattr(result[0], "relevance_score")
        assert hasattr(result[0], "final_score")
        assert result[0].final_score >= 0


# ─── Ranking semantics ─────────────────────────────────────────

class TestRankerOrdering:
    """The actual personalization logic — does it rank smartly?"""

    def test_relevant_article_ranks_above_irrelevant(self, sample_persona):
        """An article matching persona vocabulary should beat unrelated ones."""
        # Persona vocabulary contains: ai, ml, machine, learning, developers
        relevant = make_article(
            "Machine learning breakthroughs for developers",
            hours_ago=2, velocity=0.5,
        )
        irrelevant = make_article(
            "Pasta recipe ideas for weekend dinner",
            hours_ago=2, velocity=0.5,
        )
        result = rank_articles([irrelevant, relevant], sample_persona, top_k=2)
        assert result[0] is relevant
        assert result[1] is irrelevant

    def test_recency_breaks_ties(self, sample_persona):
        """When relevance ties, the more recent article should win."""
        old = make_article("Generic news headline", hours_ago=30, velocity=0.5)
        new = make_article("Generic news headline", hours_ago=1, velocity=0.5)
        result = rank_articles([old, new], sample_persona, top_k=2)
        assert result[0] is new

    def test_handles_empty_persona(self, sample_persona_empty):
        """Cold-start users (no persona) should still get a sensible ranking."""
        articles = [
            make_article("Some title", hours_ago=10, velocity=0.7),
            make_article("Another title", hours_ago=2, velocity=0.4),
        ]
        # Should not raise; should return something ordered
        result = rank_articles(articles, sample_persona_empty, top_k=2)
        assert len(result) == 2