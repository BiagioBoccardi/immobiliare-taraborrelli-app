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
    # Address search for the online estimate (OpenStreetMap Nominatim, max 1 request/second).
    geocoder_url: str = "https://nominatim.openstreetmap.org"
    geocoder_user_agent: str = "ImmobiliareTaraborrelliApp/0.1 (valutazione immobili)"
    # Contact address sent to Nominatim, as its usage policy asks for regular use.
    geocoder_email: str | None = None
    # Area preferred in the results (longitude/latitude of two corners): province of Chieti.
    geocoder_viewbox: str = "13.85,42.55,14.80,41.65"


@lru_cache
def get_settings() -> Settings:
    return Settings()
