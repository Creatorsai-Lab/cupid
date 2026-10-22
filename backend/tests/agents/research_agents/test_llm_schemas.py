"""The agent's structured outputs pass the gateway's strict-schema conversion,
which Groq's strict mode needs: every object closed, every property required."""

import copy
from typing import Any

import pytest

from app.agents.llm.gateway import _strict_schema
from app.agents.research_agents.models import PageRankBatch, ResearchPlan


def objects(node: Any):
    if isinstance(node, dict):
        if node.get("type") == "object" or "properties" in node:
            yield node
        for value in node.values():
            yield from objects(value)
    elif isinstance(node, list):
        for value in node:
            yield from objects(value)


@pytest.mark.parametrize("model", [ResearchPlan, PageRankBatch])
def test_every_object_is_closed_and_fully_required(model) -> None:
    # Break caught: Groq rejecting the agent's schemas because an object somewhere
    # (inside arrays or unions too) is open or has an optional field.
    schema = model.model_json_schema()
    before = copy.deepcopy(schema)

    strict = _strict_schema(schema)

    nodes = list(objects(strict))
    assert nodes
    for node in nodes:
        assert node["additionalProperties"] is False
        assert set(node.get("required", [])) == set(node.get("properties", {}))
    assert schema == before  # the original isn't changed
