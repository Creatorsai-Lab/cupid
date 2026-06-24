import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.config import settings
from app.earn.models import EarnOpportunity, EarnProfile  # noqa

# Import Base and ALL DB models so Alembic autogenerate sees every table.
# A model MISSING here makes autogenerate think its table was deleted and emit a
# destructive drop_table — exactly what happened to user_personalization and
# trending_articles in c7efed3e1588. Keep this list exhaustive.
from app.models.audit_log import AuditLog  # noqa
from app.models.creation_history import CreationHistory  # noqa
from app.models.insights_snapshot import InsightsSnapshot  # noqa
from app.models.persona import UserPersonalization  # noqa
from app.models.social_connection import SocialConnection  # noqa
from app.models.top_content import TopContent  # noqa
from app.models.trending_article import TrendingArticle  # noqa
from app.models.user import Base
from app.subscriptions.models import Subscription  # noqa

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This is the key line — tells Alembic what tables should exist
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a live database connection."""
    url = settings.database_url
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
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
