from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pandas as pd


class EmailSendError(Exception):
    """Raised when EAMA cannot send an alert email."""


def _get_smtp_credentials() -> tuple[str, str, str]:
    """Read sender/recipient credentials from environment variables.

    Credentials are never hard-coded or logged. Set these before using
    --send-emails:
        EAMA_SMTP_EMAIL       -- the Outlook/Office 365 address to send from
        EAMA_SMTP_PASSWORD    -- its password or app password
        EAMA_ALERT_RECIPIENT  -- where alert emails should be sent
    """
    sender_email = os.environ.get("EAMA_SMTP_EMAIL")
    sender_password = os.environ.get("EAMA_SMTP_PASSWORD")
    recipient_email = os.environ.get("EAMA_ALERT_RECIPIENT")

    missing = [
        name
        for name, value in (
            ("EAMA_SMTP_EMAIL", sender_email),
            ("EAMA_SMTP_PASSWORD", sender_password),
            ("EAMA_ALERT_RECIPIENT", recipient_email),
        )
        if not value
    ]

    if missing:
        raise EmailSendError(
            "Missing required environment variable(s) for email "
            "sending: " + ", ".join(missing) + ". Set them before "
            "using --send-emails."
        )

    return sender_email, sender_password, recipient_email


def send_alert_email(
    subject: str,
    body: str,
    smtp_server: str = "smtp.office365.com",
    smtp_port: int = 587,
) -> None:
    """Send a single alert email via Outlook/Office 365 SMTP."""
    sender_email, sender_password, recipient_email = _get_smtp_credentials()

    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = recipient_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(smtp_server, smtp_port, timeout=20) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(
                sender_email, recipient_email, message.as_string()
            )
    except smtplib.SMTPAuthenticationError as error:
        raise EmailSendError(
            "Authentication failed. If your Microsoft account uses "
            "multi-factor authentication, you likely need an app "
            "password instead of your normal password. Also confirm "
            "SMTP AUTH is enabled for this mailbox -- Microsoft "
            "disables it by default for many Office 365 tenants."
        ) from error
    except (smtplib.SMTPException, OSError) as error:
        raise EmailSendError(f"Failed to send email: {error}") from error


def send_alert_emails(drafts: pd.DataFrame) -> tuple[int, list[str]]:
    """Send every drafted email. Returns (sent_count, error_messages)."""
    if drafts.empty:
        return 0, []

    try:
        _get_smtp_credentials()
    except EmailSendError as error:
        return 0, [str(error)]

    sent_count = 0
    errors: list[str] = []

    for _, draft in drafts.iterrows():
        try:
            send_alert_email(draft["subject"], draft["body"])
            sent_count += 1
        except EmailSendError as error:
            errors.append(f"{draft['subject']}: {error}")

    return sent_count, errors