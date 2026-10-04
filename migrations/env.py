from alembic import context

from archguard.infrastructure.database.base import Base
from archguard.infrastructure.database.session import create_database
from archguard.infrastructure.logging import configure_logging
from archguard.infrastructure.settings import Settings

settings = Settings()
configure_logging(settings.log_level)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url.get_secret_value(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    database = create_database(settings.database_url)
    try:
        with database.engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        database.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
