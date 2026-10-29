import pytest

from py_common.config import BaseServiceSettings, normalize_database_url, normalize_pem

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


PEM = (
    "-----BEGIN PUBLIC KEY-----\n"
    + "\n".join(["A" * 64, "B" * 64, "C" * 20])
    + "\n-----END PUBLIC KEY-----\n"
)


@pytest.mark.parametrize(
    "pasted",
    [
        PEM,
        PEM.replace("\n", " "),  # line breaks turned into spaces by a single-line field
        PEM.replace("\n", "\\n"),  # line breaks written as \n
        "  " + PEM.replace("\n", "\r\n") + "  ",
    ],
)
def test_normalize_pem_rebuilds_the_key(pasted: str) -> None:
    assert normalize_pem(pasted) == PEM


def test_settings_normalize_the_public_key() -> None:
    settings = BaseServiceSettings(jwt_public_key=PEM.replace("\n", " "))

    assert settings.jwt_public_key == PEM


def test_normalize_pem_leaves_other_values_alone() -> None:
    assert normalize_pem("non una chiave") == "non una chiave"
