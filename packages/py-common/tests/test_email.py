import json
import smtplib
from email import message_from_bytes
from pathlib import Path
from typing import Any, ClassVar

import pytest

from py_common.config import EmailServiceSettings
from py_common.email import (
    BREVO_API_URL,
    BrevoEmailSender,
    Email,
    GmailScriptEmailSender,
    OutboxEmailSender,
    SmtpEmailSender,
    build_email_sender,
)

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


class RecordingPost:
    def __init__(self, status: int = 201, answer: bytes = b"") -> None:
        self.status = status
        self.answer = answer
        self.calls: list[tuple[str, dict[str, str], dict[str, Any], float]] = []

    def __call__(
        self, url: str, headers: dict[str, str], body: bytes, timeout: float
    ) -> tuple[int, bytes]:
        self.calls.append((url, headers, json.loads(body), timeout))
        return self.status, self.answer


async def test_brevo_sender_posts_the_email_to_the_api() -> None:
    post = RecordingPost()
    sender = BrevoEmailSender("brevo-key", "Agenzia Test <agenzia@example.test>", post=post)

    await sender.send(EMAIL)

    ((url, headers, body, timeout),) = post.calls
    assert url == BREVO_API_URL
    assert headers["api-key"] == "brevo-key"
    assert body == {
        "sender": {"email": "agenzia@example.test", "name": "Agenzia Test"},
        "to": [{"email": "anna@example.test"}],
        "subject": "Oggetto",
        "textContent": "Testo con accenti: è à.",
    }
    assert timeout == 10.0


async def test_brevo_sender_with_error_status_raises() -> None:
    sender = BrevoEmailSender("brevo-key", "agenzia@example.test", post=RecordingPost(status=401))

    with pytest.raises(RuntimeError, match="HTTP 401"):
        await sender.send(EMAIL)


def test_brevo_sender_without_sender_address_raises() -> None:
    with pytest.raises(ValueError):
        BrevoEmailSender("brevo-key", "Solo un nome")


def test_build_email_sender_chooses_the_configured_backend(tmp_path: Path) -> None:
    outbox = build_email_sender(EmailServiceSettings(email_outbox_dir=str(tmp_path)))
    brevo = build_email_sender(
        EmailServiceSettings(email_backend="brevo", brevo_api_key="brevo-key")
    )
    smtp = build_email_sender(EmailServiceSettings(email_backend="smtp", smtp_host="smtp.test"))

    assert isinstance(outbox, OutboxEmailSender)
    assert isinstance(brevo, BrevoEmailSender)
    assert isinstance(smtp, SmtpEmailSender)


def test_build_email_sender_without_credentials_refuses_to_start() -> None:
    with pytest.raises(RuntimeError, match="BREVO_API_KEY"):
        build_email_sender(EmailServiceSettings(email_backend="brevo"))
    with pytest.raises(RuntimeError, match="SMTP_HOST"):
        build_email_sender(EmailServiceSettings(email_backend="smtp"))


SCRIPT_URL = "https://script.google.com/macros/s/abc123/exec"


async def test_gmail_script_sender_posts_token_and_email() -> None:
    post = RecordingPost(status=200, answer=b'{"ok": true}')
    sender = GmailScriptEmailSender(
        SCRIPT_URL, "segreto", "Agenzia Test <agenzia@example.test>", post=post
    )

    await sender.send(EMAIL)

    ((url, _headers, body, _timeout),) = post.calls
    assert url == SCRIPT_URL
    assert body == {
        "token": "segreto",
        "to": "anna@example.test",
        "subject": "Oggetto",
        "text": "Testo con accenti: è à.",
        "senderName": "Agenzia Test",
    }


async def test_gmail_script_sender_with_refusal_in_the_body_raises() -> None:
    post = RecordingPost(status=200, answer=b'{"ok": false, "error": "unauthorized"}')
    sender = GmailScriptEmailSender(SCRIPT_URL, "sbagliato", "agenzia@example.test", post=post)

    with pytest.raises(RuntimeError, match="unauthorized"):
        await sender.send(EMAIL)


async def test_gmail_script_sender_with_non_json_answer_raises() -> None:
    post = RecordingPost(status=200, answer=b"<html>Accedi</html>")
    sender = GmailScriptEmailSender(SCRIPT_URL, "segreto", "agenzia@example.test", post=post)

    with pytest.raises(RuntimeError):
        await sender.send(EMAIL)


def test_gmail_script_sender_refuses_other_addresses() -> None:
    with pytest.raises(ValueError):
        GmailScriptEmailSender("https://example.test/hook", "segreto", "agenzia@example.test")


def test_build_email_sender_with_gmail_script() -> None:
    sender = build_email_sender(
        EmailServiceSettings(
            email_backend="gmail_script", gmail_script_url=SCRIPT_URL, gmail_script_token="t"
        )
    )

    assert isinstance(sender, GmailScriptEmailSender)


def test_build_email_sender_with_gmail_script_without_token_refuses_to_start() -> None:
    with pytest.raises(RuntimeError, match="GMAIL_SCRIPT"):
        build_email_sender(
            EmailServiceSettings(email_backend="gmail_script", gmail_script_url=SCRIPT_URL)
        )
