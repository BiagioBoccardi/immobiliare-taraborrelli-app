import pytest

from app.models.enums import LeadPriority, OwnerIntention
from app.services.priority import priority_for


@pytest.mark.parametrize(
    ("intention", "expected"),
    [
        (OwnerIntention.KNOW_VALUE, LeadPriority.LOW),
        (OwnerIntention.PLANNING, LeadPriority.MEDIUM),
        (OwnerIntention.DECIDED, LeadPriority.HIGH),
    ],
)
def test_priority_for_intention_returns_expected_priority(
    intention: OwnerIntention, expected: LeadPriority
) -> None:
    result = priority_for(intention)

    assert result is expected
