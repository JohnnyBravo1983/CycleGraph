import os
import smtplib
from email.message import EmailMessage
from typing import Any, Dict

def send_admin_alert_new_user(user: Dict[str, Any]) -> bool:
    host = os.getenv("SMTP_HOST")
    port_s = os.getenv("SMTP_PORT", "587")
    username = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")
    mail_from = os.getenv("SMTP_FROM")
    mail_to = os.getenv("ADMIN_ALERT_TO")

    if not all([host, port_s, username, password, mail_from, mail_to]):
        print("NEW_USER_ALERT skipped (missing SMTP env vars)")
        return False

    try:
        port = int(port_s)
    except Exception:
        port = 587

    msg = EmailMessage()
    msg["Subject"] = f"CycleGraph: New user signup ({user.get('uid')})"
    msg["From"] = mail_from
    msg["To"] = mail_to

    lines = [
        "New user registered:",
        f"Full name: {user.get('display_name') or user.get('full_name') or ''}",
        f"Age: {user.get('age') or ''}",
        f"Gender: {user.get('gender') or ''}",
        f"Country: {user.get('country') or ''}",
        f"City: {user.get('city') or ''}",
        f"Email: {user.get('email') or ''}",
        f"UID: {user.get('uid') or ''}",
        f"Created_at: {user.get('created_at') or ''}",
        f"Bike name: {user.get('bike_name') or ''}",
        "",
        "Note: This is an automated admin alert.",
    ]
    msg.set_content("\n".join(lines))

    try:
        with smtplib.SMTP(host, port, timeout=10) as s:
            s.ehlo()
            # STARTTLS for 587 (safe default). If provider doesn't support it, ignore.
            try:
                s.starttls()
                s.ehlo()
            except Exception:
                pass
            s.login(username, password)
            s.send_message(msg)
        return True
    except Exception as e:
        # do not leak sensitive values
        print(
            f"NEW_USER_ALERT failed uid={user.get('uid')} email={user.get('email')} "
            f"err={type(e).__name__}: {e}"
        )
        return False
