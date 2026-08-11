"""
Email service to construct and transmit SMTP messages
"""

import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Literal

from app.core import config
from app.templates.email import (
    get_registration_template,
    get_email_change_template,
    get_contact_form_template,
)

logger = logging.getLogger(__name__)


class EmailService:
    """Sends verification codes and contact form emails via SMTP"""

    def __init__(self):
        self.smtp_host = config.SMTP_HOST
        self.smtp_port = config.SMTP_PORT
        self.smtp_user = config.SMTP_USER
        self.smtp_password = config.SMTP_PASSWORD
        self.smtp_from_name = config.SMTP_FROM_NAME
        self.env = config.ENV

    def send_verification_email(
        self,
        recipient_email: str,
        code: str,
        purpose: Literal["register", "email_change"],
    ) -> None:
        """
        Retrieves templates and sends code via SMTP.
        """
        if purpose == "register":
            subject, text_content, html_content = get_registration_template(code)
        elif purpose == "email_change":
            subject, text_content, html_content = get_email_change_template(code)
        else:
            raise ValueError(f"Invalid email verification purpose: {purpose}")

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.smtp_from_name} <{self.smtp_user}>"
            msg["To"] = recipient_email

            # Attach parts
            msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))

            # Connect and send
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.smtp_user, recipient_email, msg.as_string())

            logger.info(
                "Verification email successfully sent to %s for %s",
                recipient_email,
                purpose,
            )

        except Exception as e:
            logger.exception("Failed to send email to %s: %s", recipient_email, e)
            raise RuntimeError(f"Email delivery failed: {e}") from e

    def send_contact_form_email(
        self,
        full_name: str,
        sender_email: str,
        message: str,
        target_recipient: str | None = None,
    ) -> None:
        """
        Sends contact form inquiries via SMTP to CONTACT_FORM_RECIPIENT_EMAIL.
        """
        recipient = target_recipient or config.CONTACT_FORM_RECIPIENT_EMAIL
        subject, text_content, html_content = get_contact_form_template(
            full_name=full_name,
            sender_email=sender_email,
            message=message,
        )

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.smtp_from_name} <{self.smtp_user}>"
            msg["To"] = recipient
            msg["Reply-To"] = f"{full_name} <{sender_email}>"

            msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.smtp_user, recipient, msg.as_string())

            logger.info(
                "Contact form email successfully sent from %s (%s) to %s",
                full_name,
                sender_email,
                recipient,
            )

        except Exception as e:
            logger.exception("Failed to send contact email from %s: %s", sender_email, e)
            raise RuntimeError(f"Contact email delivery failed: {e}") from e
