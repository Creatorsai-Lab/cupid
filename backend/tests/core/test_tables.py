"""Tables that libraries create (LangGraph's checkpointer, SAQ's run queue) are
invisible to Alembic, so autogenerate can never drop saved runs or queued jobs."""

from sqlalchemy import text

from app.agents.runtime.checkpoint import open_checkpointer
from app.agents.runtime.queue import make_queue
from app.core.tables import EXTERNAL_TABLES, include_name, metadata


async def test_every_library_table_is_kept_out_of_alembic(engine, test_database_url):
    async with open_checkpointer(test_database_url):
        pass  # creates its tables if missing
    queue = make_queue(test_database_url, name="tables-test")
    await queue.connect()  # creates its tables if missing
    await queue.disconnect()

    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "select table_name from information_schema.tables "
                "where table_schema = 'public'"
            )
        )
        not_ours = (
            {name for (name,) in rows} - set(metadata.tables) - {"alembic_version"}
        )

    assert not_ours == EXTERNAL_TABLES  # a new library table must be added to the list
    assert not any(include_name(name, "table", None) for name in not_ours)
    assert include_name("users", "table", None)
