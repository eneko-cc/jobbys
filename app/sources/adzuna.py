"""API Adzuna (https://developer.adzuna.com), agrégateur qui couvre la France."""

import httpx

from ..config import settings
from .base import RawOffer, find_email, strip_html

SEARCH_URL = "https://api.adzuna.com/v1/api/jobs/fr/search/1"

NAME = "Adzuna"


def enabled() -> bool:
    return bool(settings.adzuna_app_id and settings.adzuna_app_key)


def parse(item: dict) -> RawOffer:
    salary = ""
    if item.get("salary_min") and item.get("salary_max"):
        salary = f"{int(item['salary_min'])} - {int(item['salary_max'])} € / an"
    description = strip_html(item.get("description", ""))
    return RawOffer(
        source=NAME,
        external_id=str(item["id"]),
        title=strip_html(item.get("title", "")),
        company=(item.get("company") or {}).get("display_name", ""),
        location=(item.get("location") or {}).get("display_name", ""),
        description=description,
        url=item.get("redirect_url", ""),
        apply_url=item.get("redirect_url", ""),
        apply_email=find_email(description),
        contract=item.get("contract_type", "") or "",
        salary=salary,
        published_at=item.get("created", ""),
    )


def search(keywords: str, location: str = "", limit: int = 50) -> list[RawOffer]:
    params = {
        "app_id": settings.adzuna_app_id,
        "app_key": settings.adzuna_app_key,
        "what": keywords,
        "results_per_page": min(limit, 50),
        "content-type": "application/json",
    }
    if location:
        params["where"] = location
    response = httpx.get(SEARCH_URL, params=params, timeout=30)
    response.raise_for_status()
    return [parse(item) for item in response.json().get("results", [])]
