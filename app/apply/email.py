import shutil
import smtplib
import subprocess
import sys
import webbrowser
from email.message import EmailMessage
from urllib.parse import quote

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


MAIL_APP_SCRIPT = """
on run argv
    set {toAddress, theSubject, theBody, cvPath} to argv
    tell application "Mail"
        set msg to make new outgoing message with properties {subject:theSubject, content:theBody & return & return, visible:false}
        tell msg
            make new to recipient at end of to recipients with properties {address:toAddress}
            if cvPath is not "" then
                make new attachment with properties {file name:(POSIX file cvPath)} at after the last paragraph
                delay 1
            end if
        end tell
        send msg
    end tell
end run
"""


def can_use_mail_app() -> bool:
    return sys.platform == "darwin" and shutil.which("osascript") is not None


def send_with_mail_app(to: str, subject: str, body: str, profile: Profile) -> None:
    """Envoie avec l'app Mail du Mac, depuis le compte qui y est configuré. Aucun mot de passe."""
    cv = profile.cv_path
    proc = subprocess.run(
        ["osascript", "-", to, subject, body, str(cv) if cv else ""],
        input=MAIL_APP_SCRIPT, capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"L'app Mail n'a pas pu envoyer l'email : {proc.stderr.strip()[:300]}")


def open_draft(to: str, subject: str, body: str) -> None:
    """Dernier recours : ouvre un brouillon dans la messagerie par défaut (sans pièce jointe)."""
    webbrowser.open(f"mailto:{to}?subject={quote(subject)}&body={quote(body)}")


def deliver(to: str, subject: str, body: str, profile: Profile) -> tuple[str, str]:
    """Envoie la candidature par le meilleur moyen disponible. Renvoie (statut, détail)."""
    if settings.smtp_user and settings.smtp_password:
        send(build(to, subject, body, profile))
        return "sent", f"Envoyé à {to}"
    if can_use_mail_app():
        send_with_mail_app(to, subject, body, profile)
        return "sent", f"Envoyé à {to} avec l'app Mail"
    open_draft(to, subject, body)
    return "to_do", f"Brouillon ouvert pour {to} : joins ton CV et clique sur Envoyer."
