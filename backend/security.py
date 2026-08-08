import re

import bcrypt

PASSWORD_RULES = [
    (r".{8,}", "En az 8 karakter"),
    (r"[A-Z]", "En az bir büyük harf"),
    (r"[a-z]", "En az bir küçük harf"),
    (r"[0-9]", "En az bir rakam"),
    (r"[^A-Za-z0-9]", "En az bir özel karakter"),
]

PERSONAL_EMAIL_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "hotmail.com",
    "hotmail.com.tr",
    "outlook.com",
    "outlook.com.tr",
    "live.com",
    "msn.com",
    "yahoo.com",
    "yahoo.com.tr",
    "ymail.com",
    "icloud.com",
    "me.com",
    "mac.com",
    "proton.me",
    "protonmail.com",
    "pm.me",
    "yandex.com",
    "yandex.com.tr",
    "yandex.ru",
    "mail.ru",
    "inbox.ru",
    "gmx.com",
    "gmx.de",
    "aol.com",
    "zoho.com",
    "tutanota.com",
    "fastmail.com",
    "qq.com",
    "163.com",
    "126.com",
}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def validate_password(password: str) -> list[str]:
    errors = []
    for pattern, message in PASSWORD_RULES:
        if not re.search(pattern, password):
            errors.append(message)
    return errors


def validate_password_confirm(password: str, password_confirm: str) -> str | None:
    if password != password_confirm:
        return "Şifreler eşleşmiyor"
    return None


def validate_username(username: str) -> str | None:
    if len(username) < 3 or len(username) > 30:
        return "Kullanıcı adı 3-30 karakter olmalıdır"
    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        return "Kullanıcı adı sadece harf, rakam ve alt çizgi içerebilir"
    return None


def validate_email(email: str) -> str | None:
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return "Geçerli bir e-posta adresi girin"
    return None


def get_email_domain(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower().strip()


def is_personal_email(email: str) -> bool:
    return get_email_domain(email) in PERSONAL_EMAIL_DOMAINS


def validate_business_email(email: str) -> str | None:
    if err := validate_email(email):
        return err
    if is_personal_email(email):
        return "Şirket hesapları için kurumsal e-posta kullanın (Gmail, Hotmail vb. kabul edilmez)"
    return None


def get_allowed_employee_domains(owner_email: str) -> list[str]:
    from config import settings

    domains: list[str] = []
    owner_domain = get_email_domain(owner_email)
    if not is_personal_email(owner_email):
        domains.append(owner_domain)
    for part in settings.company_email_domains.split(","):
        domain = part.strip().lower()
        if domain and domain not in domains:
            domains.append(domain)
    return domains or [owner_domain]


def validate_employee_email(employee_email: str, owner_email: str) -> str | None:
    if err := validate_business_email(employee_email):
        return err
    allowed = get_allowed_employee_domains(owner_email)
    employee_domain = get_email_domain(employee_email)
    if employee_domain not in allowed:
        allowed_label = ", ".join(f"@{domain}" for domain in allowed)
        return f"Personel e-postası şirket domainlerinden biri olmalıdır ({allowed_label})"
    return None


def validate_company_name(company_name: str | None) -> str | None:
    value = (company_name or "").strip()
    if len(value) < 2:
        return "Şirket adı en az 2 karakter olmalıdır"
    if len(value) > 100:
        return "Şirket adı en fazla 100 karakter olabilir"
    return None
