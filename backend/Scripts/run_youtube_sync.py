r"""
Manual YouTube sync runner — for development testing.

Usage:
    cd D:\\Cupid\\backend
    python -m scripts.run_youtube_sync                 # sync all youtube connections
    python -m scripts.run_youtube_sync <connection_id> # sync just one
    
Note: Ensure the docker contains connections
    docker exec -it cupid_postgres psql -U cupid -d cupid_db -c "SELECT id, handle FROM social_connections;"

Run this when you want to:
    - Test that OAuth → sync pipeline works end-to-end
    - See real numbers land in the DB without waiting 6 hours
    - Debug a specific connection's sync failure
"""
import asyncio
import logging
import sys
from uuid import UUID

from sqlalchemy import select

from app.core.db import async_session as async_session_factory
from app.insights.sync import sync_connection
from app.models.social_connection import SocialConnection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)


async def main(connection_id_arg: str | None) -> int:
    print("\n=== Cupid YouTube Sync (manual run) ===\n")

    async with async_session_factory() as session:
        if connection_id_arg:
            # Sync a specific connection
            try:
                conn_id = UUID(connection_id_arg)
            except ValueError:
                print(f"ERROR: invalid UUID: {connection_id_arg}")
                return 1
            connections = [await session.get(SocialConnection, conn_id)]
            if connections[0] is None:
                print(f"ERROR: connection {conn_id} not found")
                return 1
        else:
            # Sync all youtube connections
            stmt = select(SocialConnection).where(
                SocialConnection.platform == "youtube"
            )
            connections = list((await session.execute(stmt)).scalars().all())

    if not connections:
        print("No YouTube connections found. Connect your channel first.")
        return 1

    print(f"Syncing {len(connections)} connection(s)...\n")

    ok = 0
    failed = 0
    for connection in connections:
        handle = connection.handle or connection.platform_user_id
        print(f"  → {handle} ({connection.id})")
        try:
            async with async_session_factory() as session:
                summary = await sync_connection(connection.id, session)
            print(
                f"    ✓ subscribers={summary['subscribers']} "
                f"videos={summary['videos_fetched']} "
                f"delta={summary['follower_delta']:+d}"
            )
            ok += 1
        except Exception as exc:
            print(f"    ✗ FAILED: {exc}")
            failed += 1

    print(f"\nDone. ok={ok} failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    sys.exit(asyncio.run(main(arg)))