import smtplib
from email.message import EmailMessage
from ..config import settings
from ..models import NotificationLog


def send_email(db, user, subject: str, body: str, alert_id=None):
    """Sends an email. If SMTP is not configured, the email is only logged (database + console)."""
    status, error = "logged", None
    if not settings.SMTP_HOST:
        print(f"[EMAIL-LOG] to={user.email} subject={subject}\n{body}\n")
    else:
        try:
            msg = EmailMessage()
            msg["From"], msg["To"], msg["Subject"] = settings.SMTP_FROM, user.email, subject
            msg.set_content(body)
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as s:
                s.starttls()
                if settings.SMTP_USER:
                    s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                s.send_message(msg)
            status = "sent"
        except Exception as e:  # never crash the request because of email
            status, error = "failed", str(e)
    db.add(NotificationLog(user_id=user.id, alert_id=alert_id, channel="email", subject=subject[:255],
                           body=body, status=status, error=error))
