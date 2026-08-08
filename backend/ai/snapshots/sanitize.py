import re

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+", re.I)
_PHONE_DIGITS = re.compile(r"\d{7,}")


def mask_email(value: str) -> str:
    if not value or "@" not in value:
        return value
    local, _, domain = value.partition("@")
    if not local:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


def mask_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) < 4:
        return "***"
    return f"***{digits[-4:]}"


def sanitize_text(value: str, *, include_pii: bool) -> str:
    if not value:
        return ""
    if include_pii:
        return value.strip()
    cleaned = _EMAIL_RE.sub(lambda m: mask_email(m.group(0)), value)
    cleaned = _PHONE_DIGITS.sub(lambda m: mask_phone(m.group(0)), cleaned)
    return cleaned.strip()
