"""Contracts shared by the pipeline steps: validation rules and immutability."""

import pytest
from pydantic import ValidationError

from app.agents.models import Issue, RunEvent, RunRequest
from app.agents.research_agents.models import ResearchPack, Source
from app.agents.studio_agents.models import ContentPiece, TextBlock
from app.agents.supervisor_agents.models import RunPlan


def make_request(**fields) -> RunRequest:
    defaults = {
        "run_id": "run-1",
        "user_id": "user-1",
        "prompt": "Write about testing",
        "content_type": "Text",
        "platform": "LinkedIn",
        "length": "Medium",
        "tone": "Formal",
    }
    return RunRequest.model_validate(defaults | fields)


def test_contracts_are_immutable():
    request = make_request()
    with pytest.raises(ValidationError):
        request.prompt = "changed"  # type: ignore[misc]


def test_contracts_reject_unknown_fields():
    with pytest.raises(ValidationError):
        make_request(surprise="field")


def test_request_rejects_unknown_option_values():
    with pytest.raises(ValidationError):
        make_request(tone="Sarcastic")


def test_blocked_plan_must_say_why():
    with pytest.raises(ValidationError):
        RunPlan(verdict="block")
    assert (
        RunPlan(verdict="block", reason="Prompt is empty").reason == "Prompt is empty"
    )


def test_allowed_plan_needs_deliverables():
    with pytest.raises(ValidationError):
        RunPlan(verdict="allow", deliverables=())


def test_issue_and_event_shapes():
    issue = Issue(step="research", severity="degraded", message="Low coverage")
    event = RunEvent(run_id="run-1", type="step.finished", step="research")
    assert issue.severity == "degraded"
    assert event.data == {}
    with pytest.raises(ValidationError):
        RunEvent.model_validate({"run_id": "run-1", "type": "something.else"})


def test_research_pack_sources_must_have_unique_ids():
    source = Source(id="S1", title="A", url="https://example.com/a")
    with pytest.raises(ValidationError):
        ResearchPack(status="complete", sources=(source, source))


def test_content_piece_is_addressable_blocks():
    piece = ContentPiece(
        id="p1",
        deliverable="linkedin_post",
        variant=1,
        blocks=(TextBlock(role="hook", text="Hook"), TextBlock(text="Body")),
    )
    assert [b.kind for b in piece.blocks] == ["text", "text"]
    with pytest.raises(ValidationError):
        ContentPiece(id="p2", deliverable="linkedin_post", variant=1, blocks=())
