import json
import subprocess

from app import llm
from app.sources import france_travail, web

FT_RESULTS = """
<ul><li class="result" data-id-offre="199XYZ">
  <h2><span class="media-heading-title">Chef de projet digital (H/F)</span></h2>
  <p class="subtext">ACME - <span>75 - PARIS 09</span></p>
  <p class="description">Vous pilotez des projets web.</p>
  <p class="contrat">CDI Temps plein</p>
</li></ul>
"""


def test_france_travail_site_parse():
    [offer] = france_travail.parse_site_results(FT_RESULTS)
    assert offer.external_id == "199XYZ"
    assert offer.title == "Chef de projet digital (H/F)"
    assert offer.company == "ACME"
    assert offer.location == "75 - PARIS 09"
    assert offer.url.endswith("/detail/199XYZ")


def test_france_travail_detail_parse():
    html = '<div class="description"><p>Missions.</p><p>Envoyez votre CV à rh@acme.fr</p></div>'
    description, email = france_travail.parse_site_detail(html)
    assert "Missions." in description
    assert email == "rh@acme.fr"


def fake_cli(output):
    def run(command, **kwargs):
        assert "--json-schema" in command
        assert "ANTHROPIC_API_KEY" not in kwargs["env"]
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(output), stderr="")
    return run


def test_cli_backend(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(llm, "claude_cli", lambda: "/usr/bin/claude")
    assert llm.backend() == "cli"
    monkeypatch.setattr(llm.subprocess, "run", fake_cli(
        {"is_error": False, "structured_output": {"objet": "Candidature", "message": "Bonjour"}}
    ))
    letter = llm.write_letter({"title": "Dev"}, llm.Profile(), "email")
    assert letter.message == "Bonjour"


def test_web_source(monkeypatch):
    monkeypatch.setattr(llm, "claude_cli", lambda: "/usr/bin/claude")
    monkeypatch.setattr(llm.subprocess, "run", fake_cli({"is_error": False, "structured_output": {"offres": [
        {"titre": "Chef de projet", "entreprise": "ACME", "lieu": "Paris", "site": "HelloWork",
         "url": "https://www.hellowork.com/fr-fr/emplois/1.html", "description": "Postulez : rh@acme.fr"},
        {"titre": "Sans lien", "entreprise": "X", "lieu": "", "site": "?", "url": "pas une url", "description": ""},
    ]}}))
    offers = web.search("chef de projet", "Paris")
    assert len(offers) == 1
    assert offers[0].source == "HelloWork"
    assert offers[0].apply_email == "rh@acme.fr"
