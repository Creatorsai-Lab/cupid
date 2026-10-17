"""The real Postgres checkpointer: a crashed run resumes from Postgres, and its
tables are kept out of Alembic so a migration can never drop saved runs."""

import uuid

import pytest
from langchain_core.runnables import RunnableConfig
from sqlalchemy import text

from app.agents.graph import PLACEHOLDER_STEPS, build_graph
from app.agents.runtime.checkpoint import open_checkpointer
from app.core.tables import EXTERNAL_TABLES, include_name
from tests.agents.test_contracts import make_request
from tests.agents.test_graph import Calls, steps


async def test_crashed_run_resumes_from_postgres(engine, test_database_url):
    calls = Calls()
    crashing = calls.track("research", PLACEHOLDER_STEPS.research, fail_times=1)
    thread_id = f"test-{uuid.uuid4()}"
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

    async with open_checkpointer(test_database_url) as saver:
        graph = build_graph(steps(calls, research=crashing), checkpointer=saver)
        try:
            with pytest.raises(RuntimeError, match="research crashed"):
                await graph.ainvoke(
                    {"request": make_request()}, config, durability="sync"
                )

            final = await graph.ainvoke(None, config, durability="sync")

            assert calls.count == {"supervisor": 1, "research": 2, "studio": 1}
            assert final["pieces"]
        finally:
            await saver.adelete_thread(thread_id)


async def test_checkpointer_tables_are_invisible_to_alembic(engine, test_database_url):
    async with open_checkpointer(test_database_url):
        pass  # creates the tables if missing
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "select table_name from information_schema.tables "
                "where table_schema = 'public' and table_name like 'checkpoint%'"
            )
        )
        created = {name for (name,) in rows}

    assert created == EXTERNAL_TABLES  # a new library table must be added to the list
    assert not any(include_name(name, "table", None) for name in created)
    assert include_name("users", "table", None)
