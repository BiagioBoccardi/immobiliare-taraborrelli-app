"""Email sending, same approach as the auth service (password reset codes).

Used for the notice sent to the agency when a new request arrives. When the `notification`
service exists, this moves there.

Two ways to send, chosen in the settings:
- `outbox`: each email is saved as a .eml file in a folder. Local development and tests:
  nothing leaves the computer.
- `smtp`: any email provider that offers SMTP (the provider is still to be chosen).
"""

import asyncio
import logging
import smtplib
import ssl
import uuid
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    text: str


class EmailSender(Protocol):
    async def send(self, email: Email) -> None: ...


def _message(email: Email, sender: str) -> EmailMessage:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = email.to
    message["Subject"] = email.subject
    message["Date"] = formatdate(localtime=True)
    message.set_content(email.text)
    return message


class OutboxEmailSender:
    """Saves emails as files instead of sending them."""

    def __init__(self, directory: str, sender: str) -> None:
        self._directory = Path(directory)
        self._sender = sender

    async def send(self, email: Email) -> None:
        data = _message(email, self._sender).as_bytes()
        path = self._directory / f"{uuid.uuid4()}.eml"

        def write() -> None:
            self._directory.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        await asyncio.to_thread(write)
        logger.info("email saved to the outbox", extra={"file": path.name})


class SmtpEmailSender:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        sender: str,
        use_ssl: bool = False,
        timeout: float = 10.0,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._sender = sender
        self._use_ssl = use_ssl
        self._timeout = timeout

    def _send_blocking(self, message: EmailMessage) -> None:
        context = ssl.create_default_context()
        if self._use_ssl:
            with smtplib.SMTP_SSL(
                self._host, self._port, timeout=self._timeout, context=context
            ) as client:
                self._deliver(client, message)
        else:
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as client:
                client.starttls(context=context)
                self._deliver(client, message)

    def _deliver(self, client: smtplib.SMTP, message: EmailMessage) -> None:
        if self._username:
            client.login(self._username, self._password)
        client.send_message(message)

    async def send(self, email: Email) -> None:
        await asyncio.to_thread(self._send_blocking, _message(email, self._sender))
