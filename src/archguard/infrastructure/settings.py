from enum import StrEnum
from typing import Self

from pydantic import (
    PostgresDsn,
    SecretStr,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from archguard.core.model.types import NonEmptyString


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ARCHGUARD_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        hide_input_in_errors=True,
    )

    app_name: NonEmptyString = "ArchGuard AI"
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    database_url: SecretStr = SecretStr("postgresql+psycopg://archguard@localhost:5432/archguard")
    log_level: LogLevel = LogLevel.INFO

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = TypeAdapter(PostgresDsn).validate_python(value.get_secret_value())
        except ValidationError:
            raise ValueError("database_url must be a valid PostgreSQL URL") from None
        if url.scheme != "postgresql+psycopg" or not url.path or url.path == "/":
            raise ValueError("database_url must use postgresql+psycopg and include a database name")
        return value

    @model_validator(mode="after")
    def validate_production(self) -> Self:
        if self.environment == Environment.PRODUCTION and self.debug:
            raise ValueError("debug must be disabled in production")
        return self
