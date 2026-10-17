"""Run records: created queued, status updates, ownership, the database
refusing statuses that don't exist, and the per-run execution lock."""

import uuid
from contextlib import asynccontextmanager

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.agents.runtime.models import AgentRun
from app.agents.runtime.runs import RunStore
from tests.agents.test_contracts import make_request
from tests.factories import make_user, save


@pytest.fixture
def store(db_session) -> RunStore:
    @asynccontextmanager
    async def sessions():
        yield db_session  # the test's rolled-back session; commits become savepoints

    return RunStore(sessions)


async def owned_run(db_session, store: RunStore):
    user = make_user()
    await save(db_session, user)
    request = make_request(run_id=str(uuid.uuid4()), user_id=str(user.id))
    await store.create(request)
    return user, request


async def test_new_run_is_queued_with_its_request(db_session, store):
    _, request = await owned_run(db_session, store)

    run = await store.get(request.run_id)

    assert run is not None
    assert run.status == "queued"
    assert run.request["prompt"] == request.prompt
    assert run.error is None


async def test_status_updates_are_stored(db_session, store):
    _, request = await owned_run(db_session, store)

    await store.set_status(request.run_id, "failed", error="The run failed; retry it.")
    run = await store.get(request.run_id)
    await db_session.refresh(run)

    assert (run.status, run.error) == ("failed", "The run failed; retry it.")


async def test_only_the_owner_can_load_a_run(db_session, store):
    owner, request = await owned_run(db_session, store)
    stranger = make_user()
    await save(db_session, stranger)

    assert await store.get_for_user(request.run_id, owner.id) is not None
    assert await store.get_for_user(request.run_id, stranger.id) is None
    assert await store.get_for_user("not-a-uuid", owner.id) is None


async def test_database_refuses_unknown_statuses(db_session, store):
    _, request = await owned_run(db_session, store)
    run = await store.get(request.run_id)
    assert isinstance(run, AgentRun)

    with pytest.raises(IntegrityError, match="ck_agent_runs_status"):
        run.status = "exploded"
        await db_session.flush()


async def test_only_one_resume_claim_wins(db_session, store):
    owner, request = await owned_run(db_session, store)
    await store.set_status(request.run_id, "failed", error="boom")

    first = await store.claim_for_resume(request.run_id, owner.id)
    second = await store.claim_for_resume(request.run_id, owner.id)

    assert (first, second) == (True, False)
    run = await store.get(request.run_id)
    await db_session.refresh(run)
    assert (run.status, run.error) == ("queued", None)


async def test_resume_claims_need_a_failed_run_owned_by_the_caller(db_session, store):
    owner, request = await owned_run(db_session, store)
    stranger = make_user()
    await save(db_session, stranger)

    assert await store.claim_for_resume(request.run_id, owner.id) is False  # queued
    await store.set_status(request.run_id, "failed")
    assert await store.claim_for_resume(request.run_id, stranger.id) is False
    assert await store.claim_for_resume("not-a-uuid", owner.id) is False
    assert await store.claim_for_resume(request.run_id, None) is True  # worker


async def test_only_one_execution_holds_a_run_at_a_time(engine):
    store = RunStore(async_sessionmaker(engine))  # each lock: its own connection
    run_id, other_run = str(uuid.uuid4()), str(uuid.uuid4())

    async with store.exclusive(run_id) as first:
        async with (
            store.exclusive(run_id) as second,
            store.exclusive(other_run) as third,
        ):
            assert (first, second, third) == (True, False, True)

    with pytest.raises(RuntimeError):
        async with store.exclusive(run_id):
            raise RuntimeError("step crashed")
    async with store.exclusive(run_id) as again:
        assert again  # released when the block ends, even after an error
