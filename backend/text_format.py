import re
import unicodedata

_TURKISH_LOWER_MAP = str.maketrans({"I": "ı", "İ": "i"})
_TURKISH_UPPER_FIRST = {"i": "İ", "ı": "I"}

# Google Maps / kullanıcı girişlerinde sık görülen yazım düzeltmeleri (küçük harf anahtar)
_WORD_TYPOS: dict[str, str] = {
    "kuför": "kuaför",
    "kuförü": "kuaförü",
    "kufor": "kuaför",
    "kuforu": "kuaförü",
    "kuafor": "kuaför",
    "kuaforu": "kuaförü",
    "dovme": "dövme",
    "dovmeci": "dövmeci",
    "guzellik": "güzellik",
}


def turkish_lower(text: str) -> str:
    return text.translate(_TURKISH_LOWER_MAP).lower()


def _is_latin_word(word: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9&'.-]+", word)) and not re.search(
        r"[ğüşıöçĞÜŞİÖÇ]", word
    )


def _word_lower(word: str) -> str:
    if _is_latin_word(word):
        return word.lower()
    return turkish_lower(word)


def _fix_word_spelling(word: str) -> str:
    lower = _word_lower(word)
    return _WORD_TYPOS.get(lower, lower)


def turkish_title_word(word: str) -> str:
    if not word:
        return word

    if re.fullmatch(r"[\W_]+", word):
        return word

    if "-" in word:
        parts = word.split("-")
        return "-".join(turkish_title_word(part) for part in parts)

    if "'" in word:
        parts = word.split("'")
        return "'".join(turkish_title_word(part) if part else part for part in parts)

    fixed = _fix_word_spelling(word)
    if not fixed:
        return word

    first = fixed[0]
    if _is_latin_word(word):
        first = first.upper()
    else:
        first = _TURKISH_UPPER_FIRST.get(first, first.upper())
    return first + fixed[1:]


def normalize_display_name(value: str) -> str:
    if not value or not value.strip():
        return value.strip() if value else ""

    text = unicodedata.normalize("NFKC", value.strip())
    text = re.sub(r"\s+", " ", text)
    return " ".join(turkish_title_word(word) for word in text.split(" ") if word)


def normalize_business_name(value: str) -> str:
    return normalize_display_name(value)


def normalize_person_name(value: str) -> str:
    return normalize_display_name(value)


def normalize_city_name(value: str) -> str:
    return normalize_display_name(value)


def normalize_lead_text_fields(data: dict) -> dict:
    result = dict(data)

    if result.get("isletme_adi"):
        result["isletme_adi"] = normalize_business_name(str(result["isletme_adi"]))

    if result.get("yetkili"):
        result["yetkili"] = normalize_person_name(str(result["yetkili"]))

    if result.get("sehir"):
        result["sehir"] = normalize_city_name(str(result["sehir"]))

    return result
