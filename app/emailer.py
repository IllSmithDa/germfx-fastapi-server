# app/emailer.py
from __future__ import annotations

import logging
import os
from typing import Literal

logger = logging.getLogger(__name__)

EmailProvider = Literal["resend", "ses", "console"]


def _get_provider() -> EmailProvider:
    provider = os.getenv("EMAIL_PROVIDER", "console").strip().lower()
    if provider in {"resend", "ses", "console"}:
        return provider  # type: ignore[return-value]
    return "console"


def _get_from_email() -> str:
    return os.getenv("EMAIL_FROM", "SideFX <onboarding@resend.dev>")


def _send_via_resend(to_email: str, subject: str, html: str) -> None:
    try:
        import resend
    except ImportError as e:
        raise RuntimeError("Resend SDK not installed. Run: pip install resend") from e

    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        raise RuntimeError("RESEND_API_KEY is not configured")

    resend.api_key = api_key

    params: resend.Emails.SendParams = {
        "from": _get_from_email(),
        "to": [to_email],
        "subject": subject,
        "html": html,
    }

    result = resend.Emails.send(params)
    print(result)
    logger.info("Resend send result: %s", result)


def _send_via_ses(to_email: str, subject: str, html: str) -> None:
    try:
        import boto3
    except ImportError as e:
        raise RuntimeError("boto3 is not installed. Run: pip install boto3") from e

    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    if not region:
        raise RuntimeError("AWS_REGION or AWS_DEFAULT_REGION must be configured for SES")

    client = boto3.client("ses", region_name=region)

    source = _get_from_email()
    # SES Source must be the raw email address, not "Name <email>"
    if "<" in source and ">" in source:
        source_email = source.split("<", 1)[1].split(">", 1)[0].strip()
    else:
        source_email = source.strip()

    response = client.send_email(
        Source=source_email,
        Destination={"ToAddresses": [to_email]},
        Message={
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {
                "Html": {"Data": html, "Charset": "UTF-8"},
            },
        },
    )

    logger.info("SES send result: %s", response)


def _send_via_console(to_email: str, subject: str, html: str) -> None:
    logger.info("EMAIL_PROVIDER=console")
    logger.info("To: %s", to_email)
    logger.info("Subject: %s", subject)
    logger.info("HTML:\n%s", html)


def send_email(to_email: str, subject: str, html: str) -> None:
    provider = _get_provider()

    if provider == "resend":
        _send_via_resend(to_email, subject, html)
        return

    if provider == "ses":
        _send_via_ses(to_email, subject, html)
        return

    _send_via_console(to_email, subject, html)


def verification_email_html(link: str) -> str:
    return f"""
    <html>
      <body
        style="
          margin:0;
          padding:32px 16px;
          background:#f8fafc;
          font-family:Arial,sans-serif;
          color:#111827;
        "
      >
        <table
          width="100%"
          cellpadding="0"
          cellspacing="0"
          style="max-width:600px;margin:0 auto;"
        >
          <tr>
            <td>
              <div
                style="
                  background:#ffffff;
                  border:1px solid #e5e7eb;
                  border-radius:20px;
                  padding:40px 32px;
                  box-shadow:0 1px 3px rgba(0,0,0,0.05);
                "
              >
                <div style="text-align:center;">
                  <div
                    style="
                      display:inline-block;
                      padding:6px 12px;
                      border-radius:999px;
                      background:#eff6ff;
                      color:#2563eb;
                      font-size:12px;
                      font-weight:700;
                      letter-spacing:0.08em;
                      text-transform:uppercase;
                    "
                  >
                    Welcome to SideFX
                  </div>

                  <h1
                    style="
                      margin:20px 0 12px;
                      font-size:32px;
                      line-height:1.2;
                      color:#0f172a;
                    "
                  >
                    Verify your email
                  </h1>

                  <p
                    style="
                      margin:0 auto;
                      max-width:460px;
                      font-size:16px;
                      line-height:1.7;
                      color:#475569;
                    "
                  >
                    SideFX helps you track symptoms, understand medications,
                    monitor recalls and health news, and organize important
                    health information in one place.
                  </p>
                </div>

                <div style="margin-top:36px;text-align:center;">
                  <a
                    href="{link}"
                    style="
                      display:inline-block;
                      padding:14px 24px;
                      background:#111827;
                      color:#ffffff;
                      text-decoration:none;
                      border-radius:12px;
                      font-size:15px;
                      font-weight:600;
                    "
                  >
                    Verify Email
                  </a>
                </div>

                <div
                  style="
                    margin-top:32px;
                    padding-top:24px;
                    border-top:1px solid #e5e7eb;
                  "
                >
                  <p
                    style="
                      margin:0;
                      font-size:14px;
                      line-height:1.7;
                      color:#64748b;
                    "
                  >
                    If you did not create an account, you can safely ignore
                    this email.
                  </p>

                  <p
                    style="
                      margin-top:16px;
                      font-size:13px;
                      color:#94a3b8;
                    "
                  >
                    © SideFX
                  </p>
                </div>
              </div>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """


def password_reset_email_html(link: str) -> str:
    return f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.5; color: #111827;">
        <h2>Reset your password</h2>
        <p>Click the button below to reset your password.</p>
        <p>
          <a
            href="{link}"
            style="display:inline-block;padding:10px 16px;background:#111827;color:#ffffff;text-decoration:none;border-radius:8px;"
          >
            Reset Password
          </a>
        </p>
        <p>If you did not request this, you can ignore this email.</p>
      </body>
    </html>
    """