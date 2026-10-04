from io import StringIO
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from pydantic import SecretStr
from sqlalchemy import create_engine, text

from archguard.infrastructure.database.base import Base
from archguard.infrastructure.database.session import Database, create_database


def test_postgresql_engine_is_lazy_and_masks_password(monkeypatch: pytest.MonkeyPatch) -> None:
    import psycopg

    def fail_connection(*args: object, **kwargs: object) -> None:
        raise AssertionError("engine factory must not open a connection")

    monkeypatch.setattr(psycopg, "connect", fail_connection)
    database = create_database(SecretStr("postgresql+psycopg://test:test-only@localhost/test"))
    try:
        assert database.engine.dialect.name == "postgresql"
        assert database.engine.hide_parameters is True
        assert "test-only" not in repr(database.engine)
        assert len(Base.metadata.tables) == 0
    finally:
        database.dispose()


def test_transaction_commit_and_exception_rollback() -> None:
    # SQLite exercises SQLAlchemy transaction semantics; this is not PostgreSQL integration.
    database = Database(create_engine("sqlite+pysqlite:///:memory:"))
    try:
        with database.transaction() as session:
            session.execute(text("CREATE TABLE test_records (id INTEGER PRIMARY KEY)"))
        with database.transaction() as session:
            session.execute(text("INSERT INTO test_records VALUES (1)"))
        with pytest.raises(RuntimeError, match="test rollback"), database.transaction() as session:
            session.execute(text("INSERT INTO test_records VALUES (2)"))
            raise RuntimeError("test rollback")
        with database.transaction() as session:
            assert session.execute(text("SELECT id FROM test_records")).scalars().all() == [1]
    finally:
        database.dispose()


def test_alembic_offline_without_postgresql(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "ARCHGUARD_DATABASE_URL", "postgresql+psycopg://test:test%40only@localhost/test"
    )
    output = StringIO()
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"), output_buffer=output)
    command.upgrade(config, "head", sql=True)
    assert "BEGIN" in output.getvalue()
    assert "COMMIT" in output.getvalue()
