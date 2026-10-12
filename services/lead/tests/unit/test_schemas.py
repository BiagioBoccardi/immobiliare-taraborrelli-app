import pytest
from pydantic import ValidationError

from app.schemas.lead import LeadUpdate, OwnerRequestCreate, ValuationCreate, ValuationDetails
from tests.factories import consent_payload, owner_request_payload, valuation_payload


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        ("+39 333 000 0000", "+393330000000"),
        ("0039 333-000-0000", "+393330000000"),
        ("0871 123456", "0871123456"),
    ],
)
def test_valuation_phone_is_normalized(raw: str, normalized: str) -> None:
    data = ValuationCreate.model_validate(valuation_payload(phone=raw))

    assert data.phone == normalized


@pytest.mark.parametrize("phone", ["abc", "123", "+39 333 000 0000 0000 0000"])
def test_valuation_with_invalid_phone_is_rejected(phone: str) -> None:
    with pytest.raises(ValidationError):
        ValuationCreate.model_validate(valuation_payload(phone=phone))


def test_valuation_without_privacy_consent_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ValuationCreate.model_validate(
            valuation_payload(consent=consent_payload(privacy_accepted=False))
        )


def test_valuation_with_unknown_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ValuationCreate.model_validate(valuation_payload(budget=1))


def test_owner_request_with_valuation_kind_is_rejected() -> None:
    with pytest.raises(ValidationError):
        OwnerRequestCreate.model_validate(owner_request_payload(kind="valuation"))


def test_details_with_price_and_unknown_flag_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ValuationDetails(expected_price=150_000, expected_price_unknown=True)


def test_details_all_fields_optional() -> None:
    details = ValuationDetails()

    assert details.model_dump(exclude_none=True) == {"expected_price_unknown": False}


def test_lead_update_with_naive_datetime_is_rejected() -> None:
    with pytest.raises(ValidationError):
        LeadUpdate.model_validate({"next_contact_at": "2026-10-20T10:00:00"})
