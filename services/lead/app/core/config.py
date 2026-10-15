from functools import lru_cache

from py_common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "lead"
    database_url: str = "postgresql+asyncpg://lead:lead@localhost:5432/lead"
    # How long after the first step an owner can still add optional details to a valuation.
    valuation_completion_window_days: int = 7
    # When false, events are only logged (useful to run the service without RabbitMQ).
    events_enabled: bool = True
    events_queue: str = "lead.user-deletions"


@lru_cache
def get_settings() -> Settings:
    return Settings()
