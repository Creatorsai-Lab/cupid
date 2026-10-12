"""Load every feature's models.py so Base.metadata knows all tables.

Alembic and the test database read Base.metadata; a model module that was
never imported looks like a deleted table, and autogenerate would drop it.
Discovering models.py files automatically means there is no list to forget.
"""

import importlib
from pathlib import Path

from app.core.db import Base

_APP_DIR = Path(__file__).resolve().parents[1]

for _path in sorted(_APP_DIR.rglob("models.py")):
    importlib.import_module(
        ".".join(_path.relative_to(_APP_DIR.parent).with_suffix("").parts)
    )

metadata = Base.metadata
