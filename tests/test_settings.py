import os

import pytest
from fastapi.testclient import TestClient

from app import config, main
from app.db import Database
from app.service import Jobbys


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config.Settings, "env_path", tmp_path / ".env")
    monkeypatch.setattr(config.Settings, "profile_path", tmp_path / "profile.yaml")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    for name, _ in config.ENV_KEYS.values():
        monkeypatch.delenv(name, raising=False)
    yield TestClient(main.create_app(Jobbys(Database(":memory:"))))
    for name, _ in config.ENV_KEYS.values():
        os.environ.pop(name, None)


def test_settings_roundtrip(client, tmp_path):
    body = client.get("/api/settings").json()
    assert body["settings"]["anthropic_api_key"] is False
    assert body["settings"]["email_dry_run"] is True

    body = client.put("/api/settings", json={
        "settings": {"anthropic_api_key": "sk-test", "email_dry_run": False, "adzuna_app_id": "abc"},
        "profile": {"prenom": "Alex", "mots_cles": ["chef de projet"], "salaire_min": "45000"},
    }).json()
    assert body["settings"]["anthropic_api_key"] is True  # jamais renvoyée en clair
    assert body["settings"]["email_dry_run"] is False
    assert body["profile"]["prenom"] == "Alex"
    assert body["profile"]["salaire_min"] == 45000
    env = (tmp_path / ".env").read_text()
    assert "ANTHROPIC_API_KEY=sk-test" in env and "EMAIL_DRY_RUN=false" in env
    assert client.get("/api/status").json()["claude_ready"] is True

    # Un secret laissé vide garde l'ancienne valeur, et le salaire non envoyé n'est pas effacé.
    client.put("/api/settings", json={"settings": {"anthropic_api_key": ""}, "profile": {"nom": "Martin"}})
    assert config.settings.anthropic_api_key == "sk-test"
    assert client.get("/api/settings").json()["profile"]["salaire_min"] == 45000


def test_cv_upload(client, tmp_path):
    bad = client.post("/api/cv", files={"file": ("cv.txt", b"hello", "text/plain")})
    assert bad.status_code == 400
    ok = client.post("/api/cv", files={"file": ("cv.pdf", b"%PDF-1.4 x", "application/pdf")})
    assert ok.status_code == 200
    assert (tmp_path / "cv.pdf").exists()
    assert client.get("/api/settings").json()["cv_ready"] is True
