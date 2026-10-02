from app.db import Database
from app.dedup import norm_title, same_offer
from app.sources import adzuna, france_travail, linkedin, wttj
from app.sources.base import RawOffer


def offer(title, company, location):
    return {"title": title, "company": company, "location": location}


def test_norm_title_ignores_gender_marks():
    assert norm_title("Chef de projet digital (H/F)") == norm_title("Chef de Projet Digital H/F")


def test_same_offer_rules():
    a = offer("Chef de projet digital (H/F)", "ACME SAS", "75 - Paris 9e Arrondissement")
    assert same_offer(a, offer("Chef de Projet Digital H/F", "Acme", "Paris, Ile-de-France"))
    assert not same_offer(a, offer("Chef de projet digital", "Acme", "Lyon"))
    assert not same_offer(a, offer("Développeur Python", "Acme", "Paris"))
    assert not same_offer(a, offer("Chef de projet digital", "Globex", "Paris"))


def test_cross_site_offers_are_merged(fixture_json, fixture_text):
    db = Database(":memory:")
    ft = [france_travail.parse(i) for i in fixture_json("france_travail.json")["resultats"]]
    others = [
        adzuna.parse(fixture_json("adzuna.json")["results"][0]),
        wttj.parse(fixture_json("wttj_hit.json")),
        *linkedin.parse_search(fixture_text("linkedin_search.html")),
    ]
    ids = [db.ingest(o)[0] for o in ft + others]
    assert len(set(ids)) == 2  # 4 annonces ACME fusionnées + 1 Globex
    merged = db.get_offer(ids[0])
    assert {s["source"] for s in merged["sources"]} == {
        "France Travail", "Adzuna", "Welcome to the Jungle", "LinkedIn"
    }
    assert merged["remote"] == "Télétravail partiel"  # complété par WTTJ
    assert merged["apply_email"] == "recrutement@acme.fr"


def test_same_source_twice_is_ignored():
    db = Database(":memory:")
    raw = RawOffer(source="Adzuna", external_id="1", title="Dev", company="X")
    assert db.ingest(raw) == (1, True)
    assert db.ingest(raw) == (1, False)
