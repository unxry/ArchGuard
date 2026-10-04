import pytest
from pydantic import SecretStr, ValidationError

from archguard.infrastructure.settings import Environment, LogLevel, Settings


def test_safe_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.app_name == "ArchGuard AI"
    assert settings.environment == Environment.DEVELOPMENT
    assert settings.debug is False
    assert settings.log_level == LogLevel.INFO
    assert settings.database_url.get_secret_value().startswith("postgresql+psycopg://")
    assert "postgresql" not in repr(settings.database_url)


def test_environment_reading_and_password_masking(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARCHGUARD_APP_NAME", "Test ArchGuard")
    monkeypatch.setenv("ARCHGUARD_ENVIRONMENT", "test")
    monkeypatch.setenv("ARCHGUARD_LOG_LEVEL", "WARNING")
    monkeypatch.setenv("ARCHGUARD_DATABASE_URL", "postgresql+psycopg://user:test-only@localhost/db")
    settings = Settings(_env_file=None)
    assert settings.app_name == "Test ArchGuard"
    assert settings.environment == Environment.TEST
    assert settings.log_level == LogLevel.WARNING
    assert "test-only" not in repr(settings)
    assert "test-only" not in settings.model_dump_json()


def test_env_file_is_read(tmp_path: object) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    env = tmp_path / ".env"
    env.write_text("ARCHGUARD_APP_NAME=File settings\nPOSTGRES_DB=ignored-shared-key\n")
    assert Settings(_env_file=env).app_name == "File settings"


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:///test.db",
        "postgresql://user@localhost/db",
        "invalid",
        "postgresql+psycopg://localhost",
    ],
)
def test_invalid_database_config(url: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url=SecretStr(url))


def test_production_debug_rejected() -> None:
    with pytest.raises(ValidationError, match="debug"):
        Settings(_env_file=None, environment=Environment.PRODUCTION, debug=True)
