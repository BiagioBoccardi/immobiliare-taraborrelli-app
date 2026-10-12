import pytest
from pydantic import ValidationError

from app.schemas.auth import RegisterIn
from tests.factories import register_payload


def test_register_with_short_password_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RegisterIn.model_validate(register_payload(password="corta"))


def test_register_without_privacy_consent_is_rejected() -> None:
    payload = register_payload()
    payload["consent"]["privacy_accepted"] = False

    with pytest.raises(ValidationError):
        RegisterIn.model_validate(payload)


def test_register_with_invalid_email_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RegisterIn.model_validate(register_payload(email="non-una-email"))


def test_register_normalizes_email_to_lowercase() -> None:
    data = RegisterIn.model_validate(register_payload(email="  Anna@Example.COM "))

    assert data.email == "anna@example.com"
