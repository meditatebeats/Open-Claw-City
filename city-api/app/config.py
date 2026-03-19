from functools import lru_cache
from decimal import Decimal
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    city_name: str = "OpenClaw City"
    database_url: str = "postgresql+psycopg://openclaw:openclaw@city-db:5432/openclaw_city"
    default_jurisdiction: str = "OpenClaw-Central"
    moltbook_registration_token: str | None = None
    enrollment_mode: Literal["open", "token_required"] = "token_required"
    agent_communication_channel: Literal["moltbook"] = "moltbook"
    treasury_human_confirmation_threshold: Decimal = Decimal("5000.00")

    model_config = SettingsConfigDict(env_file=".env", env_prefix="OCC_", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
