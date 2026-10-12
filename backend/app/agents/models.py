"""Shared contracts for the agent pipeline.

The request options below are the only Python definition; the router, the
pipeline state and the agents import them from here. frontend/lib/api.ts
mirrors them, and tests/agents/test_request_options.py keeps the two equal.
"""

from typing import Literal

ContentType = Literal["Text", "Image", "Article", "Video", "Ads", "Quiz"]

Platform = Literal["Twitter", "LinkedIn", "Instagram", "Facebook", "YouTube", "Web"]

ContentLength = Literal["Short", "Medium", "Long", "Full Article"]

Tone = Literal[
    "Casual",
    "Formal",
    "Informative",
    "GenZ",
    "Factual",
    "Hook First",
    "Data Driven",
    "Story Led",
    "Lifestyle",
    "Inspirational",
]
