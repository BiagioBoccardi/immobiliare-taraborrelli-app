import uuid
from datetime import UTC, datetime

from app.core.config import Settings
from app.main import build_staff_notifier
from app.models.enums import LeadKind, OwnerIntention, PropertyType
from app.services.email_templates import new_lead_email
from app.services.notifications import EmailStaffNotifier, NoStaffNotifier
from tests.factories import make_lead
from tests.unit.fakes import RecordingEmailSender

NOW = datetime(2026, 10, 28, 9, 0, tzinfo=UTC)


def _callback_lead() -> object:
    return make_lead(
        created_at=NOW,
        kind=LeadKind.CALLBACK,
        full_name="Luca Neri",
        phone="+393334445555",
        email="luca.neri@example.com",
        intention=None,
        municipality=None,
        property_type=None,
        message="Vorrei informazioni su un bilocale.",
        details={"preferred_time": "evening", "source": "website"},
    )


def test_new_lead_email_for_callback_contains_contacts_time_and_link() -> None:
    lead = _callback_lead()

    email = new_lead_email("agenzia@example.com", lead, "https://admin.example.it/leads/1")  # type: ignore[arg-type]

    assert email.to == "agenzia@example.com"
    assert email.subject == "Richiesta di ricontatto - Luca Neri"
    assert "Telefono: +393334445555" in email.text
    assert "Email: luca.neri@example.com" in email.text
    assert "Quando richiamare: Sera (17:00 - 20:00)" in email.text
    assert "Vorrei informazioni su un bilocale." in email.text
    assert "https://admin.example.it/leads/1" in email.text
    assert "Comune" not in email.text


def test_new_lead_email_for_valuation_contains_property_data() -> None:
    lead = make_lead(
        created_at=NOW,
        kind=LeadKind.VALUATION,
        municipality="Chieti",
        property_type=PropertyType.APARTMENT,
        intention=OwnerIntention.DECIDED,
    )

    email = new_lead_email("agenzia@example.com", lead, "")

    assert email.subject.startswith("Richiesta di valutazione - ")
    assert "Comune: Chieti" in email.text
    assert "Tipologia: Appartamento" in email.text
    assert "Intenzione: Ha già deciso" in email.text
    assert "pannello" not in email.text


async def test_email_staff_notifier_sends_one_email_per_recipient() -> None:
    sender = RecordingEmailSender()
    notifier = EmailStaffNotifier(
        sender, ["uno@example.com", "due@example.com"], "https://admin.example.it/"
    )
    lead = make_lead(created_at=NOW, id=uuid.UUID(int=7))

    await notifier.new_lead(lead)

    assert [email.to for email in sender.sent] == ["uno@example.com", "due@example.com"]
    assert f"https://admin.example.it/leads/{uuid.UUID(int=7)}" in sender.sent[0].text


def test_settings_split_comma_separated_notification_emails() -> None:
    settings = Settings(staff_notification_emails=" uno@example.com, ,due@example.com ")  # type: ignore[arg-type]

    assert settings.staff_notification_emails == ["uno@example.com", "due@example.com"]


def test_build_staff_notifier_without_recipients_sends_nothing() -> None:
    notifier = build_staff_notifier(Settings(staff_notification_emails=[]))

    assert isinstance(notifier, NoStaffNotifier)


def test_build_staff_notifier_with_recipients_uses_email() -> None:
    notifier = build_staff_notifier(Settings(staff_notification_emails=["a@example.com"]))

    assert isinstance(notifier, EmailStaffNotifier)
