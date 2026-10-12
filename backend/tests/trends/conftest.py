"""Fixtures used only by the trends tests."""

import pytest


@pytest.fixture
def sample_persona() -> dict:
    """A minimal persona dict — the shape the ranker expects."""
    return {
        "name": "Test User",
        "content_niche": "ai/ml",
        "target_audience": "developers and researchers",
        "bio": "I write about machine learning and software engineering.",
        "usp": "deep technical clarity for self-taught engineers",
    }


@pytest.fixture
def sample_persona_empty() -> dict:
    """An empty persona — tests the ranker's behavior on cold-start users."""
    return {}
