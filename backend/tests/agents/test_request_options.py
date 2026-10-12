"""Python and TypeScript must offer the same request options.

app/agents/models.py is the Python definition; frontend/lib/api.ts mirrors it
for the UI. If they drift, the UI offers a value the API rejects with a 422.
"""

import re
from pathlib import Path
from typing import get_args

import pytest

from app.agents.models import ContentLength, ContentType, Platform, Tone

API_TS = Path(__file__).resolve().parents[3] / "frontend" / "lib" / "api.ts"


def ts_const(name: str) -> tuple[str, ...]:
    """Read `export const NAME = [...] as const;` from api.ts."""
    match = re.search(
        rf"export const {name} = \[(.*?)\] as const;", API_TS.read_text("utf-8"), re.S
    )
    assert match, f"{name} not found in {API_TS}"
    return tuple(re.findall(r'"([^"]+)"', match.group(1)))


@pytest.mark.parametrize(
    ("ts_name", "python_type"),
    [
        ("CONTENT_TYPES", ContentType),
        ("PLATFORMS", Platform),
        ("LENGTHS", ContentLength),
        ("TONES", Tone),
    ],
)
def test_frontend_options_match_backend(ts_name, python_type):
    assert ts_const(ts_name) == get_args(python_type)
