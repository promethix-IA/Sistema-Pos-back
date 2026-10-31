import logging
import smtplib
import ssl
from email.message import EmailMessage

from shared.config.settings import settings

logger = logging.getLogger(__name__)


def mail_configured() -> bool:
    return bool(settings.smtp_user.strip() and settings.smtp_password.strip())


def send_password_reset_code(to_email: str, code: str) -> None:
    minutes = settings.password_reset_minutes
    subject = "Tu código de Promethixia"
    text = (
        f"Tu código de verificación para cambiar la contraseña es: {code}\n\n"
        f"Vence en {minutes} minutos. Si no pediste este cambio, ignora este correo."
    )
    html = f"""\
<!doctype html>
<html lang="es">
<body style="margin:0;padding:24px;background:#f4f7fb;font-family:Arial,sans-serif;color:#07111f;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:480px;margin:0 auto;background:#ffffff;border-radius:16px;border:1px solid #e2e8f0;">
    <tr>
      <td style="padding:28px 28px 8px;font-size:13px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#0d58e0;">Promethixia</td>
    </tr>
    <tr>
      <td style="padding:8px 28px 0;font-size:22px;font-weight:800;">Código de verificación</td>
    </tr>
    <tr>
      <td style="padding:12px 28px 0;font-size:15px;line-height:1.5;color:#475569;">
        Usa este código para cambiar la contraseña de tu cuenta. Vence en {minutes} minutos.
      </td>
    </tr>
    <tr>
      <td style="padding:24px 28px;">
        <div style="display:inline-block;padding:12px 20px;border-radius:12px;background:#eef4ff;color:#0a3fc0;font-size:28px;font-weight:800;letter-spacing:.28em;">{code}</div>
      </td>
    </tr>
    <tr>
      <td style="padding:0 28px 28px;font-size:13px;line-height:1.5;color:#64748b;">
        Si no pediste recuperar la contraseña, puedes ignorar este mensaje.
      </td>
    </tr>
  </table>
</body>
</html>
"""
    _send(to_email, subject, text, html)


def _send(to_email: str, subject: str, text: str, html: str) -> None:
    if not mail_configured():
        raise RuntimeError("SMTP no configurado")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from.strip() or settings.smtp_user.strip()
    message["To"] = to_email
    message.set_content(text)
    message.add_alternative(html, subtype="html")

    context = ssl.create_default_context()
    host = settings.smtp_host.strip()
    port = settings.smtp_port
    user = settings.smtp_user.strip()
    password = "".join(settings.smtp_password.split())

    def login_and_send(smtp: smtplib.SMTP) -> None:
        smtp.login(user, password)
        smtp.send_message(message)

    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=20, context=context) as smtp:
                login_and_send(smtp)
            return
        try:
            with smtplib.SMTP(host, port, timeout=20) as smtp:
                smtp.ehlo()
                smtp.starttls(context=context)
                smtp.ehlo()
                login_and_send(smtp)
        except (smtplib.SMTPServerDisconnected, smtplib.SMTPResponseException):
            with smtplib.SMTP_SSL(host, 465, timeout=20, context=context) as smtp:
                login_and_send(smtp)
    except Exception:
        logger.exception("Fallo enviando correo de recuperación")
        raise
