"""Email sending shared by the services (password reset codes, notices to the agency).

Three ways to send, chosen in the settings (EMAIL_BACKEND):
- `outbox`: each email is saved as a .eml file in a folder. Local development and tests:
  nothing leaves the computer.
- `smtp`: any email provider that offers SMTP.
- `brevo`: Brevo's HTTPS API.
- `gmail_script`: a Google Apps Script web app that sends from the Gmail account it belongs
  to (infra/email/gmail-sender.gs): no extra email provider, 100 recipients a day.
The last two use HTTPS, for hosts that block outgoing SMTP, such as Render's free plan.
"""

import asyncio
import json
import logging
import smtplib
import ssl
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate, parseaddr
from pathlib import Path
from typing import Any, Protocol

from py_common.config import EmailServiceSettings

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


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


# (url, headers, body, timeout) -> (HTTP status, response body). Replaced in tests.
HttpPost = Callable[[str, dict[str, str], bytes, float], tuple[int, bytes]]


def _http_post(url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, bytes]:
    # Only called with fixed https addresses (Brevo's API, the Apps Script web app).
    # Redirects are followed: Apps Script answers through a redirect to googleusercontent.com.
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return int(response.status), response.read(64 * 1024)
    except urllib.error.HTTPError as error:
        return int(error.code), b""


class BrevoEmailSender:
    """Sends through Brevo's transactional email API (https, port 443)."""

    def __init__(
        self,
        api_key: str,
        sender: str,
        timeout: float = 10.0,
        post: HttpPost = _http_post,
    ) -> None:
        name, address = parseaddr(sender)
        if "@" not in address:
            raise ValueError("EMAIL_FROM must contain an email address")
        self._api_key = api_key
        self._sender: dict[str, str] = {"email": address, **({"name": name} if name else {})}
        self._timeout = timeout
        self._post = post

    def _payload(self, email: Email) -> dict[str, Any]:
        return {
            "sender": self._sender,
            "to": [{"email": email.to}],
            "subject": email.subject,
            "textContent": email.text,
        }

    async def send(self, email: Email) -> None:
        body = json.dumps(self._payload(email)).encode()
        headers = {
            "api-key": self._api_key,
            "accept": "application/json",
            "content-type": "application/json",
        }
        status, _ = await asyncio.to_thread(self._post, BREVO_API_URL, headers, body, self._timeout)
        if not 200 <= status < 300:
            raise RuntimeError(f"Brevo refused the email (HTTP {status})")


class GmailScriptEmailSender:
    """Sends through a Google Apps Script web app that calls MailApp from a Gmail account.

    The script accepts {token, to, subject, text, senderName} and answers {"ok": true}; the
    token is a shared secret, so only these services can send from the account.
    """

    def __init__(
        self,
        url: str,
        token: str,
        sender: str,
        timeout: float = 20.0,
        post: HttpPost = _http_post,
    ) -> None:
        if not url.startswith("https://script.google.com/"):
            raise ValueError(
                "GMAIL_SCRIPT_URL must be the script's https://script.google.com/ address"
            )
        self._url = url
        self._token = token
        self._sender_name = parseaddr(sender)[0] or "Immobiliare Taraborrelli"
        self._timeout = timeout
        self._post = post

    async def send(self, email: Email) -> None:
        body = json.dumps(
            {
                "token": self._token,
                "to": email.to,
                "subject": email.subject,
                "text": email.text,
                "senderName": self._sender_name,
            }
        ).encode()
        headers = {"content-type": "application/json"}
        status, answer = await asyncio.to_thread(
            self._post, self._url, headers, body, self._timeout
        )
        # Apps Script always answers 200: the outcome is in the body.
        try:
            result = json.loads(answer or b"{}")
        except ValueError:
            result = {}
        if not 200 <= status < 300 or not (isinstance(result, dict) and result.get("ok") is True):
            reason = result.get("error", "unknown") if isinstance(result, dict) else "unknown"
            raise RuntimeError(f"The Gmail script did not send the email (HTTP {status}, {reason})")


def build_email_sender(settings: EmailServiceSettings) -> EmailSender:
    if settings.email_backend == "smtp":
        if not settings.smtp_host:
            raise RuntimeError("SMTP_HOST is required when EMAIL_BACKEND=smtp")
        return SmtpEmailSender(
            settings.smtp_host,
            settings.smtp_port,
            settings.smtp_username,
            settings.smtp_password,
            settings.email_from,
            use_ssl=settings.smtp_ssl,
        )
    if settings.email_backend == "brevo":
        if not settings.brevo_api_key:
            raise RuntimeError("BREVO_API_KEY is required when EMAIL_BACKEND=brevo")
        return BrevoEmailSender(settings.brevo_api_key, settings.email_from)
    if settings.email_backend == "gmail_script":
        if not settings.gmail_script_url or not settings.gmail_script_token:
            raise RuntimeError(
                "GMAIL_SCRIPT_URL and GMAIL_SCRIPT_TOKEN are required "
                "when EMAIL_BACKEND=gmail_script"
            )
        return GmailScriptEmailSender(
            settings.gmail_script_url, settings.gmail_script_token, settings.email_from
        )
    return OutboxEmailSender(settings.email_outbox_dir, settings.email_from)
