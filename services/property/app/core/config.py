from functools import lru_cache

from py_common.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "property"
    database_url: str = "postgresql+asyncpg://property:property@localhost:5432/property"
    events_enabled: bool = True

    # S3-compatible storage (MinIO in local development).
    s3_endpoint_url: str = "http://localhost:9000"
    s3_region: str = "us-east-1"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "property-media"
    # Base URL from which listing photos are served to clients (CDN or public bucket path).
    media_public_base_url: str = "http://localhost:9000/property-media"

    # Local development only: create the bucket and make listing photos readable at startup.
    s3_create_bucket: bool = False

    max_photo_bytes: int = 10 * 1024 * 1024
    max_photos_per_property: int = 40


@lru_cache
def get_settings() -> Settings:
    return Settings()
