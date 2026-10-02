"""Serveur local Jobbys : python -m app puis http://localhost:8000."""

import threading

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import ROOT, load_profile, settings
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

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
