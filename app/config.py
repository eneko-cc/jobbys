"""Réglages lus depuis le fichier .env et le profil data/profile.yaml."""

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("JOBBYS_DATA_DIR", ROOT / "data"))

load_dotenv(ROOT / ".env")


# Réglage -> (variable du fichier .env, valeur par défaut)
ENV_KEYS = {
    "anthropic_api_key": ("ANTHROPIC_API_KEY", ""),
    "anthropic_model": ("JOBBYS_MODEL", "claude-opus-5-5"),
    "france_travail_client_id": ("FRANCE_TRAVAIL_CLIENT_ID", ""),
    "france_travail_client_secret": ("FRANCE_TRAVAIL_CLIENT_SECRET", ""),
    "adzuna_app_id": ("ADZUNA_APP_ID", ""),
    "adzuna_app_key": ("ADZUNA_APP_KEY", ""),
    "enable_wttj": ("ENABLE_WTTJ", True),
    "enable_linkedin": ("ENABLE_LINKEDIN", False),
    "smtp_host": ("SMTP_HOST", "smtp.gmail.com"),
    "smtp_port": ("SMTP_PORT", 587),
    "smtp_user": ("SMTP_USER", ""),
    "smtp_password": ("SMTP_PASSWORD", ""),
    # Tant que c'est à true, les emails sont préparés mais pas envoyés.
    "email_dry_run": ("EMAIL_DRY_RUN", True),
}
SECRET_KEYS = {"anthropic_api_key", "france_travail_client_secret", "adzuna_app_key", "smtp_password"}


class Settings:
    """Lit les réglages dans l'environnement à chaque accès, pour que la page
    Réglages prenne effet sans redémarrer."""

    db_path = DATA_DIR / "jobbys.db"
    profile_path = DATA_DIR / "profile.yaml"
    browser_profile_dir = DATA_DIR / "browser"
    env_path = ROOT / ".env"

    def __getattr__(self, name: str):
        if name not in ENV_KEYS:
            raise AttributeError(name)
        env_name, default = ENV_KEYS[name]
        value = os.environ.get(env_name, "")
        if value == "":
            return default
        if isinstance(default, bool):
            return value.strip().lower() in {"1", "true", "oui", "yes", "on"}
        if isinstance(default, int):
            return int(value)
        return value

    def update(self, values: dict) -> None:
        """Enregistre des réglages dans .env et les applique tout de suite."""
        lines = self.env_path.read_text(encoding="utf-8").splitlines() if self.env_path.exists() else []
        for name, value in values.items():
            env_name = ENV_KEYS[name][0]
            if isinstance(value, bool):
                value = "true" if value else "false"
            value = str(value).replace("\n", " ").strip()
            os.environ[env_name] = value
            entry = f"{env_name}={value}"
            for i, line in enumerate(lines):
                if line.split("=", 1)[0].strip() == env_name:
                    lines[i] = entry
                    break
            else:
                lines.append(entry)
        self.env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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


def save_profile(profile: Profile, path: Path | None = None) -> None:
    path = path or settings.profile_path
    path.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(profile)
    raw = {
        "identite": {k: data[k] for k in ("prenom", "nom", "email", "telephone", "ville", "linkedin")},
        "recherche": {
            k: data[k] for k in ("mots_cles", "lieux", "teletravail", "salaire_min", "contrats", "criteres")
        },
        "cv": {"pdf": data["cv_pdf"], "texte": data["cv_texte"]},
    }
    path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
