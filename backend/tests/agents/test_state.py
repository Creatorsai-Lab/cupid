"""The run pool: who may write which field, how parallel writes merge, and that
the state survives LangGraph's checkpoint serializer unchanged."""

import operator
from typing import get_type_hints

import pytest
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from app.agents.models import Issue, RunPlan
from app.agents.research.models import ResearchPack, Source
from app.agents.state import OWNERS, RunState, check_update
from app.agents.studio.models import ContentPiece, TextBlock
from tests.agents.test_contracts import make_request


def piece(variant: int) -> ContentPiece:
    return ContentPiece(
        id=f"p{variant}",
        deliverable="linkedin_post",
        variant=variant,
        blocks=(TextBlock(text=f"Draft {variant}"),),
    )


def test_every_state_field_has_an_owner():
    assert set(get_type_hints(RunState)) == set(OWNERS)


def test_step_may_write_its_own_fields():
    update = {"plan": RunPlan(verdict="allow", deliverables=("linkedin_post",))}
    assert check_update("supervisor", update) is update


def test_step_may_not_write_another_steps_field():
    with pytest.raises(PermissionError, match="research may not write 'plan'"):
        check_update("research", {"plan": RunPlan(verdict="block", reason="x")})


def test_inputs_are_written_only_at_start():
    with pytest.raises(PermissionError):
        check_update("studio", {"request": make_request()})
    assert check_update("start", {"request": make_request()})


def test_any_step_may_report_issues():
    issue = Issue(step="studio", severity="warning", message="Shortened a draft")
    for step in ("supervisor", "research", "studio"):
        assert check_update(step, {"issues": [issue]})


def test_parallel_outputs_are_merged_not_overwritten():
    reducers = {
        name: hint.__metadata__[0]
        for name, hint in get_type_hints(RunState, include_extras=True).items()
        if hasattr(hint, "__metadata__")
    }
    assert reducers == {"pieces": operator.add, "issues": operator.add}
    assert reducers["pieces"]([piece(1)], [piece(2)]) == [piece(1), piece(2)]


def test_state_survives_the_checkpoint_serializer():
    state: RunState = {
        "request": make_request(),
        "plan": RunPlan(verdict="allow", deliverables=("linkedin_post",)),
        "research": ResearchPack(
            status="complete",
            sources=(Source(id="S1", title="A", url="https://example.com/a"),),
        ),
        "pieces": [piece(1), piece(2)],
        "issues": [Issue(step="research", severity="warning", message="One source")],
    }
    serde = JsonPlusSerializer()
    restored = serde.loads_typed(serde.dumps_typed(state))
    assert restored == state
