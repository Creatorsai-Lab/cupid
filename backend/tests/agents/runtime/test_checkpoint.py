"""Checkpoint serialization: our contract types restore cleanly and silently;
anything else is refused (strict allowlist), so tampered checkpoint data can't
make the worker build arbitrary objects."""

import logging
import os

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel

from app.agents.graph import build_graph
from app.agents.models import CreatorProfile, Issue, RunRequest
from app.agents.research_agents.models import ResearchPack, Source, SourceDocument
from app.agents.runtime.checkpoint import (
    checkpoint_serde,
    checkpoint_types,
    checkpoint_url,
)
from app.agents.studio_agents.models import ContentPiece, TextBlock
from app.agents.supervisor_agents.models import RunPlan
from tests.agents.test_contracts import make_request


def test_allowlist_covers_every_model_the_run_state_can_hold():
    assert checkpoint_types() == {
        RunRequest,
        CreatorProfile,
        RunPlan,
        ResearchPack,
        Source,
        SourceDocument,
        ContentPiece,
        TextBlock,
        Issue,
    }


async def test_full_run_restores_from_checkpoints_without_warnings(caplog):
    caplog.set_level(logging.WARNING)
    graph = build_graph(checkpointer=InMemorySaver(serde=checkpoint_serde()))
    config: RunnableConfig = {"configurable": {"thread_id": "run-1"}}

    await graph.ainvoke({"request": make_request()}, config)
    state = (await graph.aget_state(config)).values

    assert isinstance(state["plan"], RunPlan)
    assert isinstance(state["pieces"][0], ContentPiece)
    assert "unregistered type" not in caplog.text


class Intruder(BaseModel):
    payload: str


def test_types_outside_the_allowlist_are_not_rebuilt():
    serde = checkpoint_serde()
    restored = serde.loads_typed(serde.dumps_typed({"x": Intruder(payload="boom")}))
    assert not isinstance(restored["x"], Intruder)


def test_checkpoint_url_uses_the_psycopg_scheme():
    assert (
        checkpoint_url("postgresql+asyncpg://u:p@db:5432/cupid")
        == "postgresql://u:p@db:5432/cupid"
    )
    assert os.environ.get("LANGGRAPH_STRICT_MSGPACK") in (None, "", "true", "false")
