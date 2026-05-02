"""
Manual trends ingestion runner.

Use this during development instead of waiting for Celery Beat.

Usage:
    cd D:\\Cupid\\backend
    python -m scripts.test_run_ingest

    terminal command to verify:
    docker exec -it cupid_postgres psql -U cupid -d cupid_db -c "SELECT category, COUNT(*) FROM trending_articles GROUP BY category;"

What it does:
    1. Imports the same `ingest_all_categories` function Celery would call
    2. Runs it directly in the foreground
    3. Prints the per-category summary
    4. Exits

Exactly equivalent to a Celery task, just without Celery's overhead.
"""
import asyncio
import logging
import sys

from app.trends.ingest import ingest_all_categories

# Show INFO logs in the terminal — you'll see fetch progress
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


async def main() -> int:
    print("\n=== Cupid Trends Ingestion (manual run) ===\n")
    summary = await ingest_all_categories()

    print("\n=== Summary ===")
    if not summary:
        print("No categories ingested.")
        return 1

    total = 0
    for category, count in summary.items():
        print(f"  {category:<14}  {count} new")
        total += count
    print(f"\nTotal new articles: {total}")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)