"""API officielle Offres d'emploi v2 de France Travail (https://francetravail.io)."""

import httpx

from ..config import settings
from .base import RawOffer, find_email

TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
SCOPE = "api_offresdemploiv2 o2dsoffre"

NAME = "France Travail"


def enabled() -> bool:
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


def search(keywords: str, location: str = "", limit: int = 50) -> list[RawOffer]:
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
