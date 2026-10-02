"""Recherche web par Claude (via Claude Code et ton abonnement, sans clé).

Claude cherche les offres sur tout le web (HelloWork, Indeed, APEC, sites carrière...)
et renvoie les annonces trouvées. C'est ce qui couvre les sites sans API.
"""

import hashlib

from .. import llm
from .base import RawOffer, find_email

NAME = "Recherche web"

SCHEMA = {
    "type": "object",
    "properties": {
        "offres": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "titre": {"type": "string"},
                    "entreprise": {"type": "string"},
                    "lieu": {"type": "string"},
                    "url": {"type": "string"},
                    "site": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["titre", "entreprise", "lieu", "url", "site", "description"],
            },
        }
    },
    "required": ["offres"],
}

SYSTEM = (
    "Tu es un assistant de recherche d'emploi en France. Tu cherches de vraies offres publiées "
    "récemment et tu ne renvoies que des annonces individuelles (pas de pages de liste) dont tu as "
    "vu l'URL dans les résultats de recherche. N'invente rien. Dans description, résume ce que "
    "disent les résultats : missions, profil, contrat, salaire, télétravail si connus."
)


def enabled() -> bool:
    return llm.claude_cli() is not None


def search(keywords: str, location: str = "", limit: int = 15) -> list[RawOffer]:
    where = f" à {location}" if location else " en France"
    prompt = (
        f"Cherche sur le web des offres d'emploi publiées il y a moins d'un mois pour : {keywords}{where}. "
        "Couvre plusieurs sites : HelloWork, Indeed, APEC, Welcome to the Jungle, Jobteaser, Cadremploi, "
        f"sites carrière des entreprises. Donne jusqu'à {limit} offres différentes."
    )
    data = llm.run_cli(SYSTEM, prompt, SCHEMA, "sonnet", tools="WebSearch", timeout=600)
    offers = []
    for item in data.get("offres", []):
        url = item.get("url", "")
        if not url.startswith("http"):
            continue
        offers.append(
            RawOffer(
                source=item.get("site") or NAME,
                external_id=hashlib.sha1(url.encode()).hexdigest()[:16],
                title=item.get("titre", ""),
                company=item.get("entreprise", ""),
                location=item.get("lieu", ""),
                description=item.get("description", ""),
                url=url,
                apply_url=url,
                apply_email=find_email(item.get("description", "")),
            )
        )
    return offers
