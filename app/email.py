import os
import smtplib
from email.message import EmailMessage
from pathlib import Path


def send_registration_confirmation(email: str, name: str) -> None:
    subject = "Bienvenido a Reservent"
    body = (
        f"Hola {name},\n\n"
        "Tu cuenta en Reservent fue creada correctamente. "
        "Ya puedes iniciar sesión, reservar cupos, publicar eventos y validar tickets digitales.\n\n"
        "Equipo Reservent"
    )
    send_email(email, subject, body)


def send_email(to_email: str, subject: str, body: str) -> None:
    smtp_host = os.getenv("SMTP_HOST")
    if not smtp_host:
        write_dev_email(to_email, subject, body)
        return

    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD") or os.getenv("SMTP_PASS")
    mail_from = os.getenv("MAIL_FROM", smtp_user or "no-reply@reservent.local")
    use_ssl = os.getenv("SMTP_SSL", "false").lower() == "true"
    use_tls = os.getenv("SMTP_TLS", "true").lower() == "true"

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = mail_from
    message["To"] = to_email
    message.set_content(body)

    if use_ssl:
        server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
    else:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)

    with server:
        if use_tls and not use_ssl:
            server.starttls()
        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)
        server.send_message(message)


def write_dev_email(to_email: str, subject: str, body: str) -> None:
    outbox = Path(".mail_outbox")
    outbox.mkdir(exist_ok=True)
    safe_email = to_email.replace("@", "_at_").replace(".", "_")
    path = outbox / f"registration_{safe_email}.txt"
    path.write_text(f"To: {to_email}\nSubject: {subject}\n\n{body}\n", encoding="utf-8")
