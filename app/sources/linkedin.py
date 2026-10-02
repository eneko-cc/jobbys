"""Offres LinkedIn publiques, lues sans compte via les pages « invité ».

On ne se connecte jamais à ton compte : on lit seulement les offres visibles par
tout le monde. Désactivé par défaut (ENABLE_LINKEDIN=true pour l'activer).
LinkedIn limite fortement ces pages : s'il bloque, la source renvoie une erreur
et les autres continuent.
"""

import re
import time

import httpx
from bs4 import BeautifulSoup

from ..config import settings
from .base import RawOffer, find_email

SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{id}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9",
}

NAME = "LinkedIn"


def enabled() -> bool:
    return settings.enable_linkedin


def parse_search(html: str) -> list[RawOffer]:
    soup = BeautifulSoup(html, "html.parser")
    offers = []
    for card in soup.select("li"):
        urn = card.select_one("[data-entity-urn]")
        title = card.select_one(".base-search-card__title")
        if not (urn and title):
            continue
        match = re.search(r"(\d+)$", urn["data-entity-urn"])
        if not match:
            continue
        job_id = match.group(1)
        company = card.select_one(".base-search-card__subtitle")
        location = card.select_one(".job-search-card__location")
        date = card.select_one("time")
        url = f"https://www.linkedin.com/jobs/view/{job_id}/"
        offers.append(
            RawOffer(
                source=NAME,
                external_id=job_id,
                title=title.get_text(strip=True),
                company=company.get_text(strip=True) if company else "",
                location=location.get_text(strip=True) if location else "",
                url=url,
                apply_url=url,
                published_at=date.get("datetime", "") if date else "",
            )
        )
    return offers


def parse_detail(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    block = soup.select_one(".show-more-less-html__markup") or soup
    return block.get_text("\n", strip=True)


def search(keywords: str, location: str = "", limit: int = 25) -> list[RawOffer]:
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        response = client.get(
            SEARCH_URL, params={"keywords": keywords, "location": location or "France", "start": 0}
        )
        response.raise_for_status()
        offers = parse_search(response.text)[:limit]
        for offer in offers:
            time.sleep(1)  # rester discret pour ne pas se faire bloquer
            detail = client.get(DETAIL_URL.format(id=offer.external_id))
            if detail.status_code == 200:
                offer.description = parse_detail(detail.text)
                offer.apply_email = find_email(offer.description)
    return offers
