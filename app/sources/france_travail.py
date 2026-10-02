"""France Travail.

Sans clé : on lit le site candidat.francetravail.fr comme le ferait un navigateur.
Avec des identifiants francetravail.io (facultatif) : on passe par l'API officielle.
"""

import re

import httpx
from bs4 import BeautifulSoup

from ..config import settings
from .base import RawOffer, find_email

SITE_SEARCH_URL = "https://candidat.francetravail.fr/offres/recherche"
SITE_DETAIL_URL = "https://candidat.francetravail.fr/offres/recherche/detail/{id}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9",
}
TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
SCOPE = "api_offresdemploiv2 o2dsoffre"

NAME = "France Travail"


def enabled() -> bool:
    return True


def has_api_keys() -> bool:
    return bool(settings.france_travail_client_id and settings.france_travail_client_secret)


def _token(client: httpx.Client) -> str:
    response = client.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": settings.france_travail_client_id,
            "client_secret": settings.france_travail_client_secret,
            "scope": SCOPE,
        },
    )
    response.raise_for_status()
    return response.json()["access_token"]


def parse(item: dict) -> RawOffer:
    contact = item.get("contact") or {}
    origine = item.get("origineOffre") or {}
    partenaires = origine.get("partenaires") or []
    offer_id = item["id"]
    url = f"https://candidat.francetravail.fr/offres/recherche/detail/{offer_id}"
    apply_url = contact.get("urlPostulation") or origine.get("urlOrigine") or ""
    if not apply_url and partenaires:
        apply_url = partenaires[0].get("url", "")
    return RawOffer(
        source=NAME,
        external_id=offer_id,
        title=item.get("intitule", ""),
        company=(item.get("entreprise") or {}).get("nom", ""),
        location=(item.get("lieuTravail") or {}).get("libelle", ""),
        description=item.get("description", ""),
        url=url,
        apply_url=apply_url or url,
        apply_email=find_email(contact.get("courriel", ""), contact.get("coordonnees1", "")),
        contract=item.get("typeContratLibelle") or item.get("typeContrat", ""),
        salary=(item.get("salaire") or {}).get("libelle", ""),
        published_at=item.get("dateCreation", ""),
    )


def parse_site_results(html: str) -> list[RawOffer]:
    soup = BeautifulSoup(html, "html.parser")
    offers = []
    for item in soup.select("[data-id-offre]"):
        offer_id = item["data-id-offre"]
        title = item.select_one(".media-heading-title") or item.select_one("h2, h3")
        subtext = item.select_one(".subtext")
        company, location = "", ""
        if subtext:
            parts = [p.strip() for p in subtext.get_text(" ", strip=True).split(" - ", 1)]
            if len(parts) == 2:
                company, location = parts
            else:
                location = parts[0]
        contract = item.select_one(".contrat")
        url = SITE_DETAIL_URL.format(id=offer_id)
        offers.append(RawOffer(
            source=NAME,
            external_id=offer_id,
            title=title.get_text(" ", strip=True) if title else "",
            company=company,
            location=location,
            description=(item.select_one(".description").get_text(" ", strip=True)
                         if item.select_one(".description") else ""),
            url=url,
            apply_url=url,
            contract=contract.get_text(" ", strip=True) if contract else "",
        ))
    return offers


def parse_site_detail(html: str) -> tuple[str, str]:
    """Renvoie (description complète, email de candidature éventuel)."""
    soup = BeautifulSoup(html, "html.parser")
    block = soup.select_one(".description") or soup.select_one("[itemprop=description]")
    description = block.get_text("\n", strip=True) if block else ""
    contact = soup.select_one(".apply-block, #contactZone, .contact")
    email = find_email(contact.get_text(" ", strip=True) if contact else "", description)
    return description, email


def search_site(keywords: str, location: str = "", limit: int = 20) -> list[RawOffer]:
    params = {"motsCles": keywords}
    if location:
        params["lieux"] = location if location.isdigit() else ""
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        response = client.get(SITE_SEARCH_URL, params={k: v for k, v in params.items() if v})
        response.raise_for_status()
        offers = parse_site_results(response.text)
        if location and not location.isdigit():
            wanted = location.lower()
            offers = [o for o in offers if wanted in o.location.lower()] or offers
        offers = offers[:limit]
        for offer in offers:
            detail = client.get(offer.url)
            if detail.status_code == 200:
                description, email = parse_site_detail(detail.text)
                offer.description = description or offer.description
                offer.apply_email = email
    return offers


def search(keywords: str, location: str = "", limit: int = 50) -> list[RawOffer]:
    if not has_api_keys():
        return search_site(keywords, location)
    with httpx.Client(timeout=30) as client:
        token = _token(client)
        params = {"motsCles": keywords, "range": f"0-{min(limit, 150) - 1}"}
        if location.isdigit() and len(location) == 2:
            params["departement"] = location
        elif location.isdigit():
            params["commune"] = location
        response = client.get(
            SEARCH_URL,
            params=params,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        if response.status_code == 204:
            return []
        response.raise_for_status()
        offers = [parse(item) for item in response.json().get("resultats", [])]
    if location and not location.isdigit():
        # L'API filtre par code INSEE ; pour un nom de ville on filtre nous-mêmes.
        wanted = location.lower()
        offers = [o for o in offers if wanted in o.location.lower()] or offers
    return offers
