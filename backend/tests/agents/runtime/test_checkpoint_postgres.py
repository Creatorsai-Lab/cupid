"""The real Postgres checkpointer: a crashed run resumes from Postgres. (Its
tables are kept out of Alembic: tests/core/test_tables.py.)"""

import uuid

import pytest
from langchain_core.runnables import RunnableConfig

from app.agents.graph import PLACEHOLDER_STEPS, build_graph
from app.agents.runtime.checkpoint import open_checkpointer
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
