import hashlib
import html
import secrets
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, format_datetime, make_msgid

from app_timezone import local_now
from config import settings


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _from_email() -> str:
    """Gönderen adresi SMTP kullanıcısıyla aynı olmalı (DMARC/iCloud uyumu)."""
    if settings.smtp_align_from_user:
        return settings.smtp_user.strip()
    return (settings.smtp_from or settings.smtp_user).strip()


def _from_address() -> str:
    from_email = _from_email()
    from_name = (settings.smtp_from_name or "BehTech Sales Hub").strip()
    return formataddr((from_name, from_email))


def _reply_to() -> str:
    return (settings.smtp_reply_to or settings.smtp_user or settings.smtp_from).strip()


def _html_shell(title: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
</head>
<body style="margin:0;padding:0;background:#f4f6f8;font-family:Arial,Helvetica,sans-serif;color:#1f2937;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4f6f8;padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellspacing="0" cellpadding="0" style="max-width:600px;background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
          <tr>
            <td style="padding:20px 24px;background:#0f766e;color:#ffffff;font-size:18px;font-weight:700;">
              BehTech Sales Hub
            </td>
          </tr>
          <tr>
            <td style="padding:24px;font-size:15px;line-height:1.6;">
              {body_html}
            </td>
          </tr>
          <tr>
            <td style="padding:16px 24px;background:#f9fafb;border-top:1px solid #e5e7eb;font-size:12px;color:#6b7280;">
              Bu mesaj {html.escape(settings.app_url)} üzerinden otomatik gönderilmiştir.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _plain_to_html(text: str) -> str:
    parts: list[str] = []
    for block in text.strip().split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if block.startswith("http://") or block.startswith("https://"):
            safe = html.escape(block)
            parts.append(f'<p><a href="{safe}" style="color:#0f766e;">{safe}</a></p>')
            continue
        lines = block.split("\n")
        if all(line.strip().startswith("•") or line.strip().startswith("-") for line in lines if line.strip()):
            items = "".join(f"<li>{html.escape(line.strip().lstrip('•- '))}</li>" for line in lines if line.strip())
            parts.append(f"<ul style=\"margin:0 0 16px;padding-left:20px;\">{items}</ul>")
        else:
            safe_lines = "<br>".join(html.escape(line) for line in lines)
            parts.append(f"<p style=\"margin:0 0 16px;\">{safe_lines}</p>")
    return "".join(parts)


def _send_email(to_email: str, subject: str, body: str, *, html_body: str | None = None) -> None:
    from_email = _from_email()
    domain = from_email.split("@")[-1] if "@" in from_email else "behtechlabs.com"

    msg = MIMEMultipart("alternative")
    msg["From"] = _from_address()
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["Reply-To"] = _reply_to()
    msg["Date"] = format_datetime(local_now(), usegmt=False)
    msg["Message-ID"] = make_msgid(domain=domain)

    plain = body.strip()
    rendered_html = html_body or _html_shell(subject, _plain_to_html(plain))
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(rendered_html, "html", "utf-8"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(settings.smtp_user, settings.smtp_password)
        # Zarf göndereni = SMTP kullanıcısı (Google DMARC hizalaması)
        server.sendmail(settings.smtp_user, [to_email], msg.as_string())


def _send_plain_email(to_email: str, subject: str, body: str) -> None:
    _send_email(to_email, subject, body)


def send_password_reset_email(to_email: str, username: str, token: str) -> None:
    reset_url = f"{settings.app_url}/reset-password?token={token}"
    subject = "BehTech Sales Hub - Şifre Sıfırlama"
    body = f"""
Merhaba {username},

Şifre sıfırlama talebiniz alındı. Aşağıdaki bağlantıya tıklayarak yeni şifrenizi belirleyebilirsiniz:

{reset_url}

Bu bağlantı {settings.password_reset_expire_minutes} dakika geçerlidir.
Talebi siz yapmadıysanız bu e-postayı dikkate almayın.

BehTech Sales Hub
""".strip()
    _send_plain_email(to_email, subject, body)


def send_verification_email(to_email: str, username: str, token: str) -> None:
    verify_url = f"{settings.app_url}/verify-email?token={token}"
    subject = "BehTech Sales Hub - E-posta Doğrulama"
    body = f"""
Merhaba {username},

BehTech Sales Hub hesabınızı etkinleştirmek için aşağıdaki bağlantıya tıklayın:

{verify_url}

Bu bağlantı {settings.email_verification_expire_hours} saat geçerlidir.
Hesabı siz oluşturmadıysanız bu e-postayı dikkate almayın.

BehTech Sales Hub
""".strip()
    _send_plain_email(to_email, subject, body)


def send_automation_email(to_email: str, subject: str, body: str) -> None:
    if not settings.smtp_configured:
        return
    _send_plain_email(to_email, subject, body)
