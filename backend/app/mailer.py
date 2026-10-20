"""Outgoing email (password reset) over SMTP.

Configure with SMTP_HOST, SMTP_PORT (587 STARTTLS or 465 SSL), SMTP_USER, SMTP_PASSWORD and
SMTP_FROM. Without SMTP_HOST, emails are not sent and the reset link is written to the server log
instead, which is enough for local development.
"""
from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from html import escape

log = logging.getLogger("ppe.mailer")


def _cfg(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def email_enabled() -> bool:
    return bool(_cfg("SMTP_HOST"))


def app_url() -> str:
    """Public address of the app, used in emailed links. Never derived from request headers, so a
    forged Host/Origin header cannot redirect reset links to someone else's site."""
    return _cfg("APP_URL", "http://localhost:8000").rstrip("/")


def send_email(to: str, subject: str, text: str, html: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = _cfg("SMTP_FROM") or _cfg("SMTP_USER")
    msg["To"] = to
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    host, port = _cfg("SMTP_HOST"), int(_cfg("SMTP_PORT", "587"))
    user, password = _cfg("SMTP_USER"), _cfg("SMTP_PASSWORD")
    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=20) as s:
            if user:
                s.login(user, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=20) as s:
            s.starttls(context=ctx)
            if user:
                s.login(user, password)
            s.send_message(msg)


def deliver_reset_link(email: str, name: str, link: str, minutes: int) -> None:
    """Runs as a background task after the response, so timing does not reveal whether the
    email address has an account."""
    if not email_enabled():
        log.warning("SMTP not configured - password reset link for %s: %s", email, link)
        return
    who = escape(name or "there")
    text = (f"Hi {name or 'there'},\n\nSomeone (hopefully you) asked to reset your SafeSight password.\n"
            f"Open this link within {minutes} minutes to choose a new one:\n\n{link}\n\n"
            "If you didn't ask for this, you can ignore this email; your password stays the same.\n")
    html = f"""\
<div style="font-family:Segoe UI,Arial,sans-serif;background:#f3f5f7;padding:32px">
  <div style="max-width:480px;margin:auto;background:#fff;border-radius:20px;padding:32px">
    <div style="font-size:20px;font-weight:600;color:#0f766e">SafeSight</div>
    <p style="color:#0f172a;font-size:15px">Hi {who},</p>
    <p style="color:#475569;font-size:14px">Someone (hopefully you) asked to reset your SafeSight password.
       This link works once and expires in {minutes} minutes.</p>
    <p style="text-align:center;margin:28px 0">
      <a href="{escape(link)}" style="background:#0d9488;color:#fff;text-decoration:none;padding:12px 28px;
         border-radius:999px;font-weight:600;font-size:14px">Choose a new password</a></p>
    <p style="color:#94a3b8;font-size:12px">If you didn't ask for this, ignore this email; your password stays the same.</p>
  </div>
</div>"""
    try:
        send_email(email, "Reset your SafeSight password", text, html)
        log.info("password reset email sent to %s", email)
    except Exception:
        log.exception("could not send password reset email to %s", email)
