import pytest

from app.core.config import Settings


def test_settings_with_blank_initial_admin_name_uses_the_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Render sets a variable left empty in the Blueprint form to "", not unset.
    monkeypatch.setenv("INITIAL_ADMIN_NAME", "")

    settings = Settings()

    assert settings.initial_admin_name == "Amministratore"


def test_settings_strip_spaces_around_initial_admin_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INITIAL_ADMIN_EMAIL", "  admin@example.com \n")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", " password-sicura-1 \n")

    settings = Settings()

    assert (settings.initial_admin_email, settings.initial_admin_password) == (
        "admin@example.com",
        "password-sicura-1",
    )
