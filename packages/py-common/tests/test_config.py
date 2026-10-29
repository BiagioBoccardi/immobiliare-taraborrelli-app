from collections.abc import Callable

import pytest

from py_common.config import (
    BaseServiceSettings,
    describe_pem,
    normalize_database_url,
    normalize_pem,
)

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


def _real_private_key() -> str:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


def _body(pem: str) -> str:
    return "".join(line for line in pem.splitlines() if "-----" not in line)


@pytest.mark.parametrize(
    "damage",
    [
        lambda pem: f'"{pem}"',  # quotes around the key
        lambda pem: pem.replace("-----", "——"),  # dashes turned into em dashes
        lambda pem: pem.replace("-----END PRIVATE KEY-----", ""),  # END line cut off
        lambda pem: pem.replace("-----END PRIVATE KEY-----", "-----END PRIVATE KEY"),
        lambda pem: " ".join(pem.splitlines()).replace("-----BEGIN", "----BEGIN"),
        _body,  # only the base64 body
        lambda pem: " ".join(_body(pem)[i : i + 64] for i in range(0, len(_body(pem)), 64)),
    ],
)
def test_normalize_pem_with_damaged_framing_rebuilds_a_loadable_key(
    damage: Callable[[str], str],
) -> None:
    from cryptography.hazmat.primitives import serialization

    pem = _real_private_key()

    rebuilt = normalize_pem(damage(pem))

    assert rebuilt == pem
    serialization.load_pem_private_key(rebuilt.encode(), password=None)


def test_describe_pem_does_not_reveal_the_key() -> None:
    pem = _real_private_key()

    description = describe_pem(pem[:200])

    assert _body(pem)[:20] not in description
    assert "END line missing" in description
