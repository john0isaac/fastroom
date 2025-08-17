import os
from typing import ClassVar

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _bool(env_value: str | None, default: bool = False) -> bool:
    if env_value is None:
        return default
    return env_value.lower() in {"1", "true", "yes", "on"}


class Settings(BaseSettings):
    app_name: str = "Realtime Rooms API"
    redis_url: str = "redis://redis:6379/0"
    secret_key: str = os.environ.get("FASTROOM_SECRET", "dev-secret-change-me")
    access_token_exp_seconds: int = 60 * 60 * 8  # 8h
    refresh_token_exp_seconds: int = 60 * 60 * 24 * 14  # 14 days
    # debug: legacy boolean flag (true for verbose/dev behaviour). We allow users
    # to set DEBUG either as a boolean-ish value (1/true/on) or a log level
    # string (e.g. WARN, INFO, DEBUG). Non-debug levels coerce to False so that
    # existing code (e.g. SQLAlchemy echo) only enables when explicitly debug.
    debug: bool = True
    # log_level: canonical logging level. Prefer LOG_LEVEL env var; fall back to
    # DEBUG if it looks like a level string; else default INFO.
    log_level: str = (
        os.environ.get("LOG_LEVEL")
        or (os.environ.get("DEBUG") if (os.environ.get("DEBUG") or "").isalpha() else None)
        or "INFO"
    )
    test_mode: bool = _bool(os.environ.get("FASTROOM_TEST"), False)
    database_url: str = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5433/fastroom",
    )

    model_config = SettingsConfigDict(env_file=".env")

    # Accepted truthy / falsy strings for debug parsing
    _true_set: ClassVar[set[str]] = {"1", "true", "yes", "on"}
    _false_set: ClassVar[set[str]] = {"0", "false", "no", "off"}

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, v: object) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            low = v.lower()
            if low in cls._true_set:
                return True
            if low in cls._false_set:
                return False
            # Treat log level names: only DEBUG -> True, others -> False
            if low == "debug":
                return True
            return False
        # Fallback to default True if value is unexpected / None
        return True

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_level(cls, v: object) -> str:
        if isinstance(v, str) and v:
            return v.upper()
        return "INFO"


settings = Settings()
