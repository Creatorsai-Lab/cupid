"""Settings and .env.example must list the same keys.

Settings uses extra="forbid", so a key in .env that Settings doesn't know
stops the app at startup. Keeping the example file in sync with Settings
means a fresh .env copied from it always loads.
"""

from pathlib import Path

from app.config import Settings

ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"


def test_env_example_lists_exactly_the_settings_fields():
    lines = ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
    example_keys = {
        line.split("=", 1)[0].strip().lower()
        for line in lines
        if "=" in line and not line.lstrip().startswith("#")
    }
    assert example_keys == set(Settings.model_fields)
