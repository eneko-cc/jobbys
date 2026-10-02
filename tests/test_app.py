import time

import pytest
from fastapi.testclient import TestClient

from app import llm, service
from app.apply import channel_for
from app.db import Database
from app.main import create_app
from app.service import Jobbys
from app.sources.base import RawOffer

ANALYSIS = {
    "titre": "Chef de projet digital", "entreprise": "ACME", "lieu": "Paris",
    "teletravail": "Partiel", "contrat": "CDI", "salaire": "42-48 k€", "experience": "3 ans",
    "resume": "Piloter des projets web.", "missions": ["Piloter"], "profil_recherche": ["Rigueur"],
    "score": 80, "raison_score": "Bon match.", "email_candidature": "",
}


def test_channel_for():
    assert channel_for({"apply_email": "a@b.fr", "sources": []}) == "email"
    assert channel_for({"apply_url": "https://www.linkedin.com/jobs/view/1/", "sources": []}) == "linkedin"
    assert channel_for({"apply_url": "https://acme.fr/jobs", "sources": [{"source": "LinkedIn"}]}) == "linkedin"
    assert channel_for({"apply_url": "https://acme.fr/jobs", "sources": [{"source": "Adzuna"}]}) == "form"


@pytest.fixture
def setup(monkeypatch):
    db = Database(":memory:")
    jobbys = Jobbys(db)
    monkeypatch.setattr(llm, "analyze_offer", lambda offer, profile: {**ANALYSIS, "score": len(offer["title"])})
    monkeypatch.setattr(
        llm, "write_letter", lambda offer, profile, channel: llm.Letter(objet="Candidature", message="Bonjour")
    )
    sent = []
    monkeypatch.setattr(service.email_apply, "send", lambda msg: sent.append(msg))
    monkeypatch.setattr(service.settings, "email_dry_run", False)
    return TestClient(create_app(jobbys)), jobbys, sent


def wait_for(predicate, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def test_swipe_flow(setup):
    client, jobbys, sent = setup
    jobbys.db.ingest(RawOffer(source="A", external_id="1", title="Court", company="X", apply_email="rh@x.fr"))
    jobbys.db.ingest(RawOffer(source="A", external_id="2", title="Intitulé plus long", company="Y"))
    jobbys.analyze_pending()

    first = client.get("/api/offers/next").json()["offer"]
    assert first["title"] == "Intitulé plus long"  # meilleur score d'abord
    assert client.post(f"/api/offers/{first['id']}/swipe", json={"direction": "pass"}).status_code == 200
    assert client.post(f"/api/offers/{first['id']}/swipe", json={"direction": "pass"}).status_code == 409

    second = client.get("/api/offers/next").json()["offer"]
    app_id = client.post(f"/api/offers/{second['id']}/swipe", json={"direction": "like"}).json()["application_id"]
    assert wait_for(lambda: jobbys.db.get_application(app_id)["status"] == "sent")
    assert sent[0]["To"] == "rh@x.fr"
    assert client.get("/api/offers/next").json()["offer"] is None
    apps = client.get("/api/applications").json()["applications"]
    assert apps[0]["channel"] == "email" and apps[0]["message"] == "Bonjour"


def test_email_dry_run(setup, monkeypatch):
    client, jobbys, sent = setup
    monkeypatch.setattr(service.settings, "email_dry_run", True)
    offer_id, _ = jobbys.db.ingest(RawOffer(source="A", external_id="1", title="Poste", company="X", apply_email="rh@x.fr"))
    jobbys.analyze_pending()
    app_id = jobbys.like(offer_id)
    assert wait_for(lambda: jobbys.db.get_application(app_id)["status"] == "dry_run")
    assert sent == []


def test_status_endpoint(setup):
    client, _, _ = setup
    body = client.get("/api/status").json()
    assert body["counts"] == {"ready": 0, "analyzing": 0, "liked": 0, "passed": 0}
