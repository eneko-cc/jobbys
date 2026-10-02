"""Réglages lus depuis le fichier .env et le profil data/profile.yaml."""

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("JOBBYS_DATA_DIR", ROOT / "data"))

load_dotenv(ROOT / ".env")


def _flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "oui", "yes", "on"}


@dataclass
class Settings:
    db_path: Path = DATA_DIR / "jobbys.db"
    profile_path: Path = DATA_DIR / "profile.yaml"

    anthropic_model: str = os.environ.get("JOBBYS_MODEL", "claude-opus-5-5")

    france_travail_client_id: str = os.environ.get("FRANCE_TRAVAIL_CLIENT_ID", "")
    france_travail_client_secret: str = os.environ.get("FRANCE_TRAVAIL_CLIENT_SECRET", "")
    adzuna_app_id: str = os.environ.get("ADZUNA_APP_ID", "")
    adzuna_app_key: str = os.environ.get("ADZUNA_APP_KEY", "")
    enable_wttj: bool = _flag("ENABLE_WTTJ", True)
    enable_linkedin: bool = _flag("ENABLE_LINKEDIN", False)

    smtp_host: str = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user: str = os.environ.get("SMTP_USER", "")
    smtp_password: str = os.environ.get("SMTP_PASSWORD", "")
    # Tant que c'est à true, les emails sont préparés mais pas envoyés.
    email_dry_run: bool = _flag("EMAIL_DRY_RUN", True)

    browser_profile_dir: Path = DATA_DIR / "browser"


settings = Settings()


@dataclass
class Profile:
    prenom: str = ""
    nom: str = ""
    email: str = ""
    telephone: str = ""
    ville: str = ""
    linkedin: str = ""
    mots_cles: list[str] = field(default_factory=list)
    lieux: list[str] = field(default_factory=list)
    teletravail: str = ""
    salaire_min: int | None = None
    contrats: list[str] = field(default_factory=list)
    criteres: str = ""
    cv_pdf: str = ""
    cv_texte: str = ""

    @property
    def cv_path(self) -> Path | None:
        if not self.cv_pdf:
            return None
        path = Path(self.cv_pdf)
        if not path.is_absolute():
            path = DATA_DIR / path
        return path if path.exists() else None

    def cv_as_text(self) -> str:
        if self.cv_texte.strip():
            return self.cv_texte
        path = self.cv_path
        if path is None:
            return ""
        from pypdf import PdfReader

        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)

    def search_summary(self) -> str:
        lines = [
            f"Postes recherchés : {', '.join(self.mots_cles) or 'non précisé'}",
            f"Lieux : {', '.join(self.lieux) or 'non précisé'}",
            f"Télétravail souhaité : {self.teletravail or 'non précisé'}",
            f"Salaire minimum : {self.salaire_min or 'non précisé'}",
            f"Contrats : {', '.join(self.contrats) or 'non précisé'}",
        ]
        if self.criteres.strip():
            lines.append(f"Autres critères : {self.criteres.strip()}")
        return "\n".join(lines)


def load_profile(path: Path | None = None) -> Profile:
    path = path or settings.profile_path
    if not path.exists():
        return Profile()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    identite = raw.get("identite", {}) or {}
    recherche = raw.get("recherche", {}) or {}
    cv = raw.get("cv", {}) or {}
    return Profile(
        prenom=identite.get("prenom", ""),
        nom=identite.get("nom", ""),
        email=identite.get("email", ""),
        telephone=str(identite.get("telephone", "") or ""),
        ville=identite.get("ville", ""),
        linkedin=identite.get("linkedin", ""),
        mots_cles=list(recherche.get("mots_cles", []) or []),
        lieux=list(recherche.get("lieux", []) or []),
        teletravail=recherche.get("teletravail", "") or "",
        salaire_min=recherche.get("salaire_min"),
        contrats=list(recherche.get("contrats", []) or []),
        criteres=recherche.get("criteres", "") or "",
        cv_pdf=cv.get("pdf", "") or "",
        cv_texte=cv.get("texte", "") or "",
    )
