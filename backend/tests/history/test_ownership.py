"""A user can only see, edit and delete their own history entries.

Ownership is enforced in the SQL WHERE clause; another user's entry behaves as
if it doesn't exist (404), so its existence isn't revealed.
"""

from sqlalchemy import select

from app.history.models import CreationHistory
from tests.factories import make_history, make_user, save

EDIT = {
    "variants": [{"angle": "", "platform": "X", "content": "Edited", "char_count": 6}]
}


async def test_list_shows_only_my_entries(db_client, db_session, sign_in):
    me, other = make_user(), make_user()
    await save(db_session, me, other, make_history(me), make_history(other))
    sign_in(me)

    response = await db_client.get("/api/v1/history/")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [e["prompt"] for e in body["entries"]] == ["Write a post about testing"]


async def test_cannot_edit_another_users_entry(db_client, db_session, sign_in):
    me, other = make_user(), make_user()
    theirs = make_history(other)
    await save(db_session, me, other, theirs)
    sign_in(me)

    response = await db_client.patch(f"/api/v1/history/{theirs.id}", json=EDIT)

    assert response.status_code == 404
    await db_session.refresh(theirs)
    assert theirs.variants[0]["content"] == "Draft"


async def test_cannot_delete_another_users_entry(db_client, db_session, sign_in):
    me, other = make_user(), make_user()
    theirs = make_history(other)
    await save(db_session, me, other, theirs)
    sign_in(me)

    response = await db_client.delete(f"/api/v1/history/{theirs.id}")

    assert response.status_code == 404
    still_there = await db_session.scalar(
        select(CreationHistory).where(CreationHistory.id == theirs.id)
    )
    assert still_there is not None


async def test_owner_can_edit_and_delete(db_client, db_session, sign_in):
    me = make_user()
    mine = make_history(me)
    await save(db_session, me, mine)
    sign_in(me)

    assert (
        await db_client.patch(f"/api/v1/history/{mine.id}", json=EDIT)
    ).status_code == 204
    await db_session.refresh(mine)
    assert mine.variants[0]["content"] == "Edited"

    assert (await db_client.delete(f"/api/v1/history/{mine.id}")).status_code == 204
    gone = await db_session.scalar(
        select(CreationHistory).where(CreationHistory.id == mine.id)
    )
    assert gone is None
