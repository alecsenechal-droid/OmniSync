from __future__ import annotations

import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage


SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
NOTIFY_SERVICE = "OmniSync Notify"


def _get_app_password(smtp_user: str) -> str | None:
    try:
        import keyring
        return keyring.get_password(NOTIFY_SERVICE, smtp_user)
    except Exception:
        return None


def store_app_password(smtp_user: str, app_password: str) -> bool:
    try:
        import keyring
        keyring.set_password(NOTIFY_SERVICE, smtp_user, app_password)
        return True
    except Exception:
        return False


def send_failure(
    to_email: str,
    smtp_user: str,
    reason: str,
    details: str = "",
) -> bool:
    """Envoie un email d'échec via Gmail SMTP. Retourne True si envoyé."""
    app_password = _get_app_password(smtp_user)
    if not app_password:
        return False

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    subject = f"[OmniSync] Échec de la sync — {now}"
    body = (
        f"OmniSync n'a pas pu synchroniser tes données ce matin.\n\n"
        f"Raison : {reason}\n"
    )
    if details:
        body += f"\nDétails :\n{details}\n"
    body += (
        "\n— Que faire ?\n"
        "1. Ouvre PowerShell dans C:\\Users\\alecs\\Desktop\\Omnisync\n"
        "2. Lance : run.bat doctor\n"
        "3. Si le problème persiste : run.bat run --scrape-only\n\n"
        "Google Calendar n'a pas été modifié lors de ce run.\n"
    )

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = smtp_user
        msg["To"] = to_email
        msg.set_content(body)
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx) as smtp:
            smtp.login(smtp_user, app_password)
            smtp.send_message(msg)
        return True
    except Exception as exc:
        print(f"[NOTIFY] Erreur envoi: {exc}")
        return False


def notify_if_configured(reason: str, details: str = "") -> None:
    """Charge la config et envoie un email si les notifs sont configurées."""
    try:
        from .config import load_settings
        s = load_settings()
        if not s.notify_email or not s.notify_smtp_user:
            return
        sent = send_failure(s.notify_email, s.notify_smtp_user, reason, details)
        if sent:
            print(f"[NOTIFY] Email d'échec envoyé à {s.notify_email}")
        else:
            print("[NOTIFY] Email non envoyé (App Password manquant ou erreur SMTP)")
    except Exception as exc:
        print(f"[NOTIFY] Impossible d'envoyer la notification: {exc}")
