"""Format commun des offres renvoyées par chaque source."""

import html
import re
from dataclasses import dataclass, field

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


@dataclass
class RawOffer:
    source: str
    external_id: str
    title: str
    company: str = ""
    location: str = ""
    description: str = ""
    url: str = ""
    apply_url: str = ""
    apply_email: str = ""
    contract: str = ""
    salary: str = ""
    remote: str = ""
    published_at: str = ""
    extra: dict = field(default_factory=dict)


def strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>|</p>|</li>", "\n", text or "", flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


def find_email(*texts: str) -> str:
    for text in texts:
        if not text:
            continue
        match = EMAIL_RE.search(text)
        if match:
            return match.group(0).rstrip(".")
    return ""
