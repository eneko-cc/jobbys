from app.sources import adzuna, france_travail, linkedin, wttj


def test_france_travail_parse(fixture_json):
    items = fixture_json("france_travail.json")["resultats"]
    first, second = (france_travail.parse(i) for i in items)
    assert first.title == "Chef de projet digital (H/F)"
    assert first.company == "ACME SAS"
    assert first.apply_email == "recrutement@acme.fr"
    assert first.salary.startswith("Annuel")
    assert second.apply_email == ""
    assert second.apply_url == "https://globex.example/careers/po"


def test_adzuna_parse(fixture_json):
    offer = adzuna.parse(fixture_json("adzuna.json")["results"][0])
    assert offer.title == "Chef de Projet Digital H/F"
    assert offer.external_id == "4455667788"
    assert offer.salary == "42000 - 48000 € / an"


def test_wttj_parse(fixture_json):
    offer = wttj.parse(fixture_json("wttj_hit.json"))
    assert offer.url == "https://www.welcometothejungle.com/fr/companies/acme/jobs/chef-de-projet-digital_paris"
    assert offer.remote == "Télétravail partiel"
    assert "Piloter les projets" in offer.description
    assert offer.location == "Paris"


def test_linkedin_parse(fixture_text):
    offers = linkedin.parse_search(fixture_text("linkedin_search.html"))
    assert len(offers) == 1
    assert offers[0].external_id == "4012345678"
    assert offers[0].title == "Chef de projet digital H/F"
    assert offers[0].company == "ACME"
