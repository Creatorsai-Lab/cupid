import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.config import settings

# core.tables imports every feature's models.py, so autogenerate sees every
# table. A model that is never imported looks deleted and autogenerate emits a
# destructive drop_table (what happened in c7efed3e1588); discovery prevents it.
from app.core.tables import include_name, metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This is the key line — tells Alembic what tables should exist
target_metadata = metadata


def run_migrations_offline() -> None:
    """Run migrations without a live database connection."""
    url = settings.database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations with a live async database connection."""
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
