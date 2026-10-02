import smtplib
from email.message import EmailMessage

from ..config import Profile, settings


def build(to: str, subject: str, body: str, profile: Profile) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = f"{profile.prenom} {profile.nom} <{settings.smtp_user or profile.email}>".strip()
    msg["To"] = to
    msg["Subject"] = subject
    if profile.email:
        msg["Reply-To"] = profile.email
    msg.set_content(body)
    cv = profile.cv_path
    if cv is not None:
        msg.add_attachment(
            cv.read_bytes(),
            maintype="application",
            subtype="pdf",
            filename=f"CV {profile.prenom} {profile.nom}.pdf".replace("  ", " "),
        )
    return msg


def send(msg: EmailMessage) -> None:
    if not (settings.smtp_user and settings.smtp_password):
        raise RuntimeError("SMTP_USER / SMTP_PASSWORD manquants dans .env")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)
