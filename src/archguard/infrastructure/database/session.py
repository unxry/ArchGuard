from collections.abc import Iterator
from contextlib import contextmanager

from pydantic import SecretStr
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


class Database:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self._sessions = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        with self._sessions() as session, session.begin():
            yield session

    def dispose(self) -> None:
        self.engine.dispose()


def create_database(database_url: SecretStr) -> Database:
    """Construct lazily: a PostgreSQL connection is opened only by a caller using the engine."""
    return Database(
        create_engine(database_url.get_secret_value(), pool_pre_ping=True, hide_parameters=True)
    )
