"""Envoi d'une candidature après un like.

- email : envoi automatique (CV en pièce jointe) ;
- form : le formulaire s'ouvre dans un navigateur, prérempli, tu cliques sur « Envoyer » ;
- linkedin : l'offre s'ouvre, le message est prêt à copier, tu postules toi-même.
"""

from urllib.parse import urlparse


def channel_for(offer: dict) -> str:
    sources = {s["source"] for s in offer.get("sources", [])}
    host = urlparse(offer.get("apply_url") or "").netloc.lower()
    if offer.get("apply_email"):
        return "email"
    if "linkedin.com" in host or sources == {"LinkedIn"}:
        return "linkedin"
    return "form"
