"""/api/v1/agents/runs/{id}/events and /resume: owner only (others get 404 so a
run's existence never leaks), live events, safe resume of failed runs."""

import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import pytest
from fakeredis import FakeAsyncRedis

from app.agents.deps import get_event_stream, get_run_queue, get_run_store
from app.agents.models import RunEvent
from app.agents.runtime.events import EventStream
from app.agents.runtime.runs import RunStore
from app.main import app
from tests.agents.test_contracts import make_request
from tests.factories import make_user, save


@dataclass
class FakeQueue:
    jobs: list = field(default_factory=list)
    accept: bool = True

    async def enqueue(self, job):
        if not self.accept:
            return None
        self.jobs.append(job)
        return job


@pytest.fixture
async def services(db_session):
    @asynccontextmanager
    async def sessions():
        yield db_session

    redis = FakeAsyncRedis(decode_responses=True)
    store, events, queue = RunStore(sessions), EventStream(redis), FakeQueue()
    app.dependency_overrides[get_run_store] = lambda: store
    app.dependency_overrides[get_event_stream] = lambda: events
    app.dependency_overrides[get_run_queue] = lambda: queue
    yield store, events, queue
    await redis.aclose()


async def owned_run(db_session, store: RunStore, status: str = "running"):
    user = make_user()
    await save(db_session, user)
    request = make_request(run_id=str(uuid.uuid4()), user_id=str(user.id))
    await store.create(request)
    await store.set_status(request.run_id, status)  # type: ignore[arg-type]
    return user, request.run_id


def events_url(run_id: str) -> str:
    return f"/api/v1/agents/runs/{run_id}/events"


def resume_url(run_id: str) -> str:
    return f"/api/v1/agents/runs/{run_id}/resume"


# ── Events ─────────────────────────────────────────────────────


async def test_owner_receives_the_live_events(db_client, db_session, sign_in, services):
    store, events, _ = services
    user, run_id = await owned_run(db_session, store)
    for type_ in ("run.started", "run.completed"):
        await events.publish(RunEvent.model_validate({"run_id": run_id, "type": type_}))
    sign_in(user)

    response = await db_client.get(events_url(run_id))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    types = [line for line in response.text.splitlines() if line.startswith("event:")]
    assert types == ["event: run.started", "event: run.completed"]


async def test_reconnect_with_last_event_id_skips_seen_events(
    db_client, db_session, sign_in, services
):
    store, events, _ = services
    user, run_id = await owned_run(db_session, store)
    seen = await events.publish(
        RunEvent.model_validate({"run_id": run_id, "type": "run.started"})
    )
    await events.publish(
        RunEvent.model_validate({"run_id": run_id, "type": "run.completed"})
    )
    sign_in(user)

    response = await db_client.get(events_url(run_id), headers={"Last-Event-ID": seen})

    assert "event: run.started" not in response.text
    assert "event: run.completed" in response.text


@pytest.mark.parametrize("target", ["someone_elses", "unknown"])
async def test_events_are_hidden_from_everyone_but_the_owner(
    db_client, db_session, sign_in, services, target
):
    store, _, _ = services
    _, run_id = await owned_run(db_session, store)
    stranger = make_user()
    await save(db_session, stranger)
    sign_in(stranger)

    url = events_url(run_id if target == "someone_elses" else str(uuid.uuid4()))
    response = await db_client.get(url)

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "not_found", "message": "Run not found"}
    }


# ── Resume ─────────────────────────────────────────────────────


async def test_failed_run_is_queued_for_resume(
    db_client, db_session, sign_in, services
):
    store, _, queue = services
    user, run_id = await owned_run(db_session, store, status="failed")
    sign_in(user)

    response = await db_client.post(resume_url(run_id))

    assert response.status_code == 202
    assert response.json() == {"run_id": run_id, "status": "queued"}
    assert queue.jobs[0].key.startswith(f"{run_id}:manual-")
    assert queue.jobs[0].kwargs["request"] is None  # resumes from the checkpoint


async def test_only_failed_runs_can_be_resumed(
    db_client, db_session, sign_in, services
):
    store, _, queue = services
    user, run_id = await owned_run(db_session, store, status="completed")
    sign_in(user)

    response = await db_client.post(resume_url(run_id))

    assert response.status_code == 409
    assert queue.jobs == []


async def test_double_resume_queues_once(db_client, db_session, sign_in, services):
    store, _, queue = services
    user, run_id = await owned_run(db_session, store, status="failed")
    sign_in(user)

    first = await db_client.post(resume_url(run_id))
    second = await db_client.post(resume_url(run_id))

    assert (first.status_code, second.status_code) == (202, 409)
    assert len(queue.jobs) == 1


async def test_resume_of_someone_elses_run_is_not_found(
    db_client, db_session, sign_in, services
):
    store, _, queue = services
    _, run_id = await owned_run(db_session, store, status="failed")
    stranger = make_user()
    await save(db_session, stranger)
    sign_in(stranger)

    assert (await db_client.post(resume_url(run_id))).status_code == 404
    assert queue.jobs == []


async def test_queue_outage_reports_503_and_keeps_the_run_resumable(
    db_client, db_session, sign_in, services
):
    store, _, queue = services
    queue.accept = False
    user, run_id = await owned_run(db_session, store, status="failed")
    sign_in(user)

    response = await db_client.post(resume_url(run_id))

    assert response.status_code == 503
    run = await store.get(run_id)
    await db_session.refresh(run)
    assert run.status == "failed"  # the user can retry
