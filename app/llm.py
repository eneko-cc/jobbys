"""Appels à Claude : résumé + score de chaque offre, et message de candidature."""

from typing import Literal

import anthropic
from pydantic import BaseModel, Field

from .config import Profile, settings

# Si Claude refuse une requête, l'API la relance d'elle-même sur un autre modèle.
FALLBACK = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}

_client: anthropic.Anthropic | None = None
_client_key = ""


def client() -> anthropic.Anthropic:
    """Client réutilisé, recréé si la clé change dans les Réglages."""
    global _client, _client_key
    key = settings.anthropic_api_key
    if not key:
        raise RuntimeError("Clé API Claude manquante : renseigne-la dans Réglages.")
    if _client is None or key != _client_key:
        _client, _client_key = anthropic.Anthropic(api_key=key), key
    return _client


class OfferAnalysis(BaseModel):
    titre: str = Field(description="Intitulé du poste, court et clair")
    entreprise: str
    lieu: str = Field(description="Ville (et département si connu)")
    teletravail: Literal["Complet", "Partiel", "Ponctuel", "Aucun", "Non précisé"]
    contrat: str = Field(description="CDI, CDD, freelance, stage, alternance... ou 'Non précisé'")
    salaire: str = Field(description="Fourchette telle qu'annoncée, ou 'Non précisé'")
    experience: str = Field(description="Expérience demandée, ou 'Non précisé'")
    resume: str = Field(description="Une ou deux phrases : ce que fait l'entreprise et le rôle")
    missions: list[str] = Field(description="3 à 5 missions principales, phrases courtes")
    profil_recherche: list[str] = Field(description="3 à 5 attentes clés sur le candidat")
    score: int = Field(description="Correspondance avec le candidat, de 0 à 100")
    raison_score: str = Field(description="Une phrase qui explique le score (points forts et manques)")
    email_candidature: str = Field(
        description="Adresse email à laquelle envoyer la candidature si l'offre le demande explicitement, sinon chaîne vide"
    )


class Letter(BaseModel):
    objet: str = Field(description="Objet de l'email de candidature")
    message: str = Field(description="Le message de candidature complet, signé")


def _candidate(profile: Profile) -> str:
    cv = profile.cv_as_text().strip() or "CV non fourni."
    return (
        f"Candidat : {profile.prenom} {profile.nom}\n"
        f"{profile.search_summary()}\n\n"
        f"CV :\n{cv[:12000]}"
    )


def analyze_offer(offer: dict, profile: Profile) -> dict:
    system = (
        "Tu aides un candidat à trier des offres d'emploi en France. Pour chaque offre, tu extrais "
        "les informations utiles et tu notes de 0 à 100 à quel point elle correspond à ce qu'il "
        "cherche et à son CV. Sois honnête : un poste hors de ses critères (lieu, télétravail, "
        "contrat, salaire, métier) doit avoir un score bas. Si le profil du candidat est vide, "
        "note seulement la clarté et l'attractivité de l'offre et dis-le dans raison_score. "
        "Réponds en français, sans inventer ce que l'offre ne dit pas.\n\n" + _candidate(profile)
    )
    text = (
        f"Intitulé : {offer['title']}\nEntreprise : {offer.get('company') or 'inconnue'}\n"
        f"Lieu : {offer.get('location') or 'inconnu'}\nContrat : {offer.get('contract') or '?'}\n"
        f"Salaire : {offer.get('salary') or '?'}\nTélétravail : {offer.get('remote') or '?'}\n\n"
        f"Description :\n{(offer.get('description') or '')[:15000]}"
    )
    response = client().beta.messages.parse(
        model=settings.anthropic_model,
        max_tokens=4000,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": text}],
        output_format=OfferAnalysis,
        output_config={"effort": "low"},
        **FALLBACK,
    )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise RuntimeError(f"Analyse impossible ({response.stop_reason})")
    result = response.parsed_output.model_dump()
    result["score"] = max(0, min(100, result["score"]))
    return result


def write_letter(offer: dict, profile: Profile, channel: str) -> Letter:
    analysis = offer.get("analysis") or {}
    where = {
        "email": "Il sera envoyé par email, CV en pièce jointe.",
        "form": "Il sera collé dans le champ « message » ou « lettre de motivation » d'un formulaire.",
        "linkedin": "Il sera collé dans la candidature LinkedIn : reste court (moins de 1200 caractères).",
    }[channel]
    system = (
        "Tu écris des messages de candidature en français pour le candidat ci-dessous. "
        "Le message est personnalisé pour l'offre : il cite 2 ou 3 éléments précis de l'offre et "
        "les relie à des expériences réelles du CV. Ton direct et chaleureux, sans formules "
        "creuses ni superlatifs, 150 à 250 mots, vouvoiement. N'invente aucune expérience. "
        "Termine par une formule de politesse simple et la signature (prénom nom, téléphone, email).\n\n"
        + _candidate(profile)
        + f"\nTéléphone : {profile.telephone}\nEmail : {profile.email}"
    )
    text = (
        f"{where}\n\nOffre : {offer['title']} chez {offer.get('company') or 'entreprise inconnue'} "
        f"({offer.get('location') or 'lieu inconnu'})\n"
        f"Résumé : {analysis.get('resume', '')}\nMissions : {'; '.join(analysis.get('missions', []))}\n"
        f"Profil recherché : {'; '.join(analysis.get('profil_recherche', []))}\n\n"
        f"Description complète :\n{(offer.get('description') or '')[:15000]}"
    )
    response = client().beta.messages.parse(
        model=settings.anthropic_model,
        max_tokens=8000,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": text}],
        output_format=Letter,
        output_config={"effort": "medium"},
        **FALLBACK,
    )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise RuntimeError(f"Rédaction impossible ({response.stop_reason})")
    return response.parsed_output
