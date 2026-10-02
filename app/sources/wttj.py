"""Welcome to the Jungle.

Pas d'API publique : le site interroge un index Algolia avec une clé de recherche
publique, que l'on récupère sur la page d'accueil. Si le site change, cette source
peut casser : l'erreur s'affiche alors dans l'interface sans bloquer les autres.
"""

import re

import httpx

from ..config import settings
from .base import RawOffer, find_email, strip_html

HOME_URL = "https://www.welcometothejungle.com/fr/jobs"
INDEX = "wttj_jobs_production_fr"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36",
    "Referer": "https://www.welcometothejungle.com/",
    "Origin": "https://www.welcometothejungle.com",
}

NAME = "Welcome to the Jungle"

REMOTE_LABELS = {
    "fulltime": "Télétravail complet",
    "full": "Télétravail complet",
    "partial": "Télétravail partiel",
    "punctual": "Télétravail ponctuel",
    "no": "Pas de télétravail",
}


def enabled() -> bool:
    return settings.enable_wttj


def _algolia_keys(client: httpx.Client) -> tuple[str, str]:
    page = client.get(HOME_URL, headers=HEADERS).text
    app_id = re.search(r'ALGOLIA_APPLICATION_ID"\s*:\s*"([^"]+)"', page)
    api_key = re.search(r'ALGOLIA_API_KEY_CLIENT"\s*:\s*"([^"]+)"', page)
    if not (app_id and api_key):
        raise RuntimeError("Clés Algolia introuvables sur welcometothejungle.com")
    return app_id.group(1), api_key.group(1)


def _join(value) -> str:
    if isinstance(value, list):
        return "\n".join(f"- {strip_html(str(v))}" for v in value if v)
    return strip_html(str(value or ""))


def parse(hit: dict) -> RawOffer:
    org = hit.get("organization") or {}
    offices = hit.get("offices") or []
    city = offices[0].get("city", "") if offices else ""
    url = f"https://www.welcometothejungle.com/fr/companies/{org.get('slug', '')}/jobs/{hit.get('slug', '')}"
    parts = [
        _join(hit.get("summary")),
        "Missions :\n" + _join(hit.get("key_missions")) if hit.get("key_missions") else "",
        _join(hit.get("description")),
        "Profil :\n" + _join(hit.get("profile")) if hit.get("profile") else "",
    ]
    description = "\n\n".join(p for p in parts if p)
    salary = ""
    if hit.get("salary_minimum") and hit.get("salary_maximum"):
        salary = f"{hit['salary_minimum']} - {hit['salary_maximum']} {hit.get('salary_currency') or '€'}"
    return RawOffer(
        source=NAME,
        external_id=str(hit.get("reference") or hit.get("objectID") or hit.get("slug")),
        title=hit.get("name", ""),
        company=org.get("name", ""),
        location=city,
        description=description,
        url=url,
        apply_url=url,
        apply_email=find_email(description),
        contract=hit.get("contract_type", "") or "",
        salary=salary,
        remote=REMOTE_LABELS.get(hit.get("remote") or "", hit.get("remote") or ""),
        published_at=hit.get("published_at", "") or "",
    )


def search(keywords: str, location: str = "", limit: int = 50) -> list[RawOffer]:
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        app_id, api_key = _algolia_keys(client)
        query = f"{keywords} {location}".strip()
        response = client.post(
            f"https://{app_id.lower()}-dsn.algolia.net/1/indexes/{INDEX}/query",
            headers={
                **HEADERS,
                "X-Algolia-Application-Id": app_id,
                "X-Algolia-API-Key": api_key,
            },
            json={"query": query, "hitsPerPage": min(limit, 100)},
        )
        response.raise_for_status()
        return [parse(hit) for hit in response.json().get("hits", [])]
