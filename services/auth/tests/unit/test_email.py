import smtplib
from email import message_from_bytes
from pathlib import Path
from typing import Any, ClassVar

import pytest

from app.services.email import Email, OutboxEmailSender, SmtpEmailSender
from app.services.email_templates import password_reset_email

EMAIL = Email(to="anna@example.test", subject="Oggetto", text="Testo con accenti: è à.")


async def test_outbox_sender_saves_the_email_as_a_file(tmp_path: Path) -> None:
    sender = OutboxEmailSender(str(tmp_path / "outbox"), "Agenzia <noreply@example.test>")

    await sender.send(EMAIL)

    (saved,) = (tmp_path / "outbox").glob("*.eml")
    message = message_from_bytes(saved.read_bytes())
    assert message["To"] == "anna@example.test"
    assert message["From"] == "Agenzia <noreply@example.test>"
    assert message.get_payload(decode=True).decode().strip() == "Testo con accenti: è à."


class FakeSmtp:
    instances: ClassVar[list["FakeSmtp"]] = []

    def __init__(self, host: str, port: int, **kwargs: Any) -> None:
        self.host, self.port = host, port
        self.calls: list[str] = []
        self.sent: list[Any] = []
        FakeSmtp.instances.append(self)

    def __enter__(self) -> "FakeSmtp":
        return self

    def __exit__(self, *args: object) -> None:
        self.calls.append("quit")

    def starttls(self, context: Any) -> None:
        self.calls.append("starttls")

    def login(self, username: str, password: str) -> None:
        self.calls.append(f"login:{username}")

    def send_message(self, message: Any) -> None:
        self.sent.append(message)


async def test_smtp_sender_uses_starttls_and_login(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeSmtp.instances.clear()
    monkeypatch.setattr(smtplib, "SMTP", FakeSmtp)
    sender = SmtpEmailSender("smtp.example.test", 587, "user", "secret", "noreply@example.test")

    await sender.send(EMAIL)

    (client,) = FakeSmtp.instances
    assert (client.host, client.port) == ("smtp.example.test", 587)
    assert client.calls == ["starttls", "login:user", "quit"]
    assert client.sent[0]["Subject"] == "Oggetto"


async def test_smtp_sender_with_ssl_uses_smtp_ssl(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeSmtp.instances.clear()
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSmtp)
    sender = SmtpEmailSender("smtp.example.test", 465, "", "", "noreply@example.test", use_ssl=True)

    await sender.send(EMAIL)

    (client,) = FakeSmtp.instances
    assert client.calls == ["quit"]  # no login without credentials, no STARTTLS on SSL
    assert len(client.sent) == 1


def test_password_reset_email_is_in_italian_with_code_and_validity() -> None:
    email = password_reset_email("anna@example.test", "Anna Bianchi", "654321", 15)

    assert email.subject == "Il tuo codice per reimpostare la password"
    assert "654321" in email.text
    assert "15 minuti" in email.text
    assert "ignora questa email" in email.text
