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

# Tables that exist in the database but are owned by a library, not our models
# (LangGraph's Postgres checkpointer creates and migrates these itself).
EXTERNAL_TABLES = frozenset(
    {"checkpoints", "checkpoint_blobs", "checkpoint_writes", "checkpoint_migrations"}
)


def include_name(name: str | None, type_: str, parent_names: object) -> bool:
    """Alembic filter: never generate migrations for tables we don't own.

    Without it, autogenerate sees the checkpoint tables as "not in the models"
    and emits drop_table, deleting every saved run.
    """
    return not (type_ == "table" and name in EXTERNAL_TABLES)
