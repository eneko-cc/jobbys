"""Serveur local Jobbys : python -m app puis http://localhost:8000."""

import threading
from dataclasses import asdict

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import llm
from .config import DATA_DIR, ENV_KEYS, ROOT, SECRET_KEYS, Profile, load_profile, save_profile, settings
from .db import Database
from .service import Jobbys

STATIC = ROOT / "app" / "static"


def create_app(jobbys: Jobbys | None = None) -> FastAPI:
    jobbys = jobbys or Jobbys(Database(settings.db_path))
    app = FastAPI(title="Jobbys")
    app.state.jobbys = jobbys

    class Swipe(BaseModel):
        direction: str  # "like" ou "pass"

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/api/status")
    def status():
        profile = load_profile()
        return {
            "counts": jobbys.db.counts(),
            "fetch": jobbys.fetch_state,
            "profile_ready": bool(profile.mots_cles),
            "claude_ready": llm.backend() is not None,
            "claude_mode": llm.backend(),
            "email_dry_run": settings.email_dry_run,
        }

    @app.post("/api/fetch")
    def fetch():
        threading.Thread(target=jobbys.fetch, daemon=True).start()
        return {"started": True}

    @app.get("/api/offers/next")
    def next_offer():
        return {"offer": jobbys.db.next_offer()}

    @app.post("/api/offers/{offer_id}/swipe")
    def swipe(offer_id: int, body: Swipe):
        offer = jobbys.db.get_offer(offer_id)
        if offer is None:
            raise HTTPException(404, "Offre inconnue")
        if offer["status"] != "new":
            raise HTTPException(409, "Offre déjà traitée")
        if body.direction == "like":
            return {"application_id": jobbys.like(offer_id)}
        if body.direction == "pass":
            jobbys.db.set_status(offer_id, "passed")
            return {"ok": True}
        raise HTTPException(400, "direction doit valoir like ou pass")

    @app.get("/api/applications")
    def applications():
        return {"applications": jobbys.db.applications()}

    @app.get("/api/settings")
    def get_settings():
        values = {}
        for name in ENV_KEYS:
            value = getattr(settings, name)
            # Les secrets ne repartent jamais vers la page : on dit seulement s'ils sont remplis.
            values[name] = bool(value) if name in SECRET_KEYS else value
        profile = load_profile()
        return {"settings": values, "profile": asdict(profile), "cv_ready": profile.cv_path is not None}

    @app.put("/api/settings")
    def put_settings(body: dict):
        updates = {}
        for name, value in (body.get("settings") or {}).items():
            if name not in ENV_KEYS:
                continue
            if name in SECRET_KEYS and not value:
                continue  # champ secret laissé vide : on garde l'ancienne valeur
            updates[name] = value
        if updates:
            settings.update(updates)
        if body.get("profile") is not None:
            current = asdict(load_profile())
            fields = {k: v for k, v in body["profile"].items() if k in current}
            if "salaire_min" in fields:
                try:
                    fields["salaire_min"] = int(fields["salaire_min"]) if fields["salaire_min"] else None
                except (ValueError, TypeError):
                    fields.pop("salaire_min")
            save_profile(Profile(**{**current, **fields}))
        return get_settings()

    @app.post("/api/cv")
    async def upload_cv(file: UploadFile):
        content = await file.read()
        if not content.startswith(b"%PDF"):
            raise HTTPException(400, "Le CV doit être un fichier PDF")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        (DATA_DIR / "cv.pdf").write_bytes(content)
        profile = load_profile()
        profile.cv_pdf = "cv.pdf"
        save_profile(profile)
        return {"ok": True}

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
