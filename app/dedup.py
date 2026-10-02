"""Repérage des doublons entre sites.

Deux offres sont la même si l'entreprise est la même, la ville compatible, et les
intitulés très proches une fois nettoyés (accents, « H/F », ponctuation...).
"""

import re
import unicodedata
from difflib import SequenceMatcher

COMPANY_NOISE = {
    "sas", "sasu", "sa", "sarl", "eurl", "group", "groupe", "france", "inc", "ltd",
    "gmbh", "the", "et", "and", "co",
}
TITLE_NOISE = {"h", "f", "hf", "fh", "x", "m", "w", "d", "cdi", "cdd", "stage", "alternance", "e"}


def _ascii(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9+#]+", _ascii(text))


def norm_company(company: str) -> str:
    return " ".join(w for w in _words(company) if w not in COMPANY_NOISE)


def norm_title(title: str) -> str:
    title = re.sub(r"\([^)]*\)", " ", title or "")
    return " ".join(sorted(w for w in _words(title) if w not in TITLE_NOISE))


def norm_city(location: str) -> str:
    words = [w for w in _words(location) if not w.isdigit() and w not in {"france", "cedex"}]
    return words[0] if words else ""


def same_offer(a: dict, b: dict) -> bool:
    """a et b : dicts avec title, company, location."""
    company_a, company_b = norm_company(a["company"]), norm_company(b["company"])
    if not company_a or not company_b:
        return False
    if company_a != company_b and SequenceMatcher(None, company_a, company_b).ratio() < 0.9:
        return False
    city_a, city_b = norm_city(a["location"]), norm_city(b["location"])
    if city_a and city_b and city_a != city_b:
        return False
    title_a, title_b = norm_title(a["title"]), norm_title(b["title"])
    return title_a == title_b or SequenceMatcher(None, title_a, title_b).ratio() >= 0.85
