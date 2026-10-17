"""The run queue on real Postgres: the two guarantees we chose it for.

1. A job being run is never handed out again (SAQ's Redis backend can: its
   sweep re-queues a job caught between dequeue and being marked active).
2. One active job per run: other jobs of that run wait until it finishes.
"""

import uuid

import pytest
from saq import Status
from saq.queue.postgres import PostgresQueue

from app.agents.runtime.queue import enqueue_run, make_queue


@pytest.fixture
async def queue(engine, test_database_url):
    q = make_queue(test_database_url, name=f"test-{uuid.uuid4().hex[:8]}")
    assert isinstance(q, PostgresQueue)
    await q.connect()
    yield q
    async with q.pool.connection() as conn:
        await conn.execute("DELETE FROM saq_jobs WHERE queue = %s", [q.name])
    await q.disconnect()


async def test_a_job_being_run_is_never_handed_out_again(queue):
    run_id = str(uuid.uuid4())
    assert await enqueue_run(queue, run_id)

    job = await queue.dequeue(timeout=1)  # taken and marked active in one statement
    assert job is not None and job.status == Status.ACTIVE

    assert await queue.sweep() == []
    assert await queue.dequeue(timeout=0.5) is None
    assert not await enqueue_run(queue, run_id)  # same attempt can't be queued twice


async def test_only_one_job_per_run_is_active(queue):
    run_id, other_run = str(uuid.uuid4()), str(uuid.uuid4())
    assert await enqueue_run(queue, run_id)
    assert await enqueue_run(queue, run_id, attempt="manual-1")
    assert await enqueue_run(queue, other_run)

    first = await queue.dequeue(timeout=1)
    second = await queue.dequeue(timeout=1)
    assert first is not None and second is not None
    assert {first.kwargs["run_id"], second.kwargs["run_id"]} == {run_id, other_run}
    assert await queue.dequeue(timeout=0.5) is None  # run_id's other job waits

    mine = first if first.kwargs["run_id"] == run_id else second
    await queue.finish(mine, Status.COMPLETE)

    waiting = await queue.dequeue(timeout=1)
    assert waiting is not None and waiting.key == f"{run_id}:manual-1"
