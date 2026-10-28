import pytest

from py_common.config import BaseServiceSettings, normalize_database_url

NEON = (
    "postgresql://neondb_owner:secret@ep-cool-sun-a1b2c3d4-pooler.eu-central-1.aws.neon.tech"
    "/lead?sslmode=require&channel_binding=require"
)


def test_neon_address_becomes_asyncpg_direct_with_ssl() -> None:
    url = normalize_database_url(NEON)

    assert url == (
        "postgresql+asyncpg://neondb_owner:secret@ep-cool-sun-a1b2c3d4.eu-central-1.aws.neon.tech"
        "/lead?ssl=require"
    )


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("postgres://u:p@db.example.test/auth", "postgresql+asyncpg://u:p@db.example.test/auth"),
        (
            "postgresql+asyncpg://dev:dev@localhost:55432/lead",
            "postgresql+asyncpg://dev:dev@localhost:55432/lead",
        ),
        (
            "postgresql://u:p@h/db?sslmode=disable&application_name=lead",
            "postgresql+asyncpg://u:p@h/db?application_name=lead",
        ),
        ("sqlite:///./test.db", "sqlite:///./test.db"),
    ],
)
def test_other_addresses_are_adapted_or_kept(given: str, expected: str) -> None:
    assert normalize_database_url(given) == expected


def test_settings_normalize_the_database_url() -> None:
    settings = BaseServiceSettings(database_url=NEON)

    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.database_url.endswith("?ssl=require")
