import os
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from app.apply.form import prefill  # noqa: E402

FORM = Path(__file__).parent / "fixtures" / "form.html"


def test_prefill_fills_fields_without_submitting(tmp_path):
    cv = tmp_path / "cv.pdf"
    cv.write_bytes(b"%PDF-1.4 test")
    job = {
        "url": FORM.as_uri(),
        "message": "Bonjour, je candidate.",
        "cv_path": str(cv),
        "profile": {"prenom": "Alex", "nom": "Martin", "nom_complet": "Alex Martin",
                    "email": "alex@example.com", "telephone": "0600000000", "ville": "", "linkedin": ""},
    }
    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None)
        except Exception as exc:
            pytest.skip(f"Chromium indisponible : {exc}")
        page = browser.new_page()
        filled = prefill(page, job)
        assert set(filled) == {"prenom", "nom", "email", "telephone", "message", "cv"}
        assert page.input_value("#fn") == "Alex"
        assert page.input_value("#ln") == "Martin"
        assert page.input_value("textarea") == "Bonjour, je candidate."
        assert page.evaluate("window.submitted") is None
        browser.close()
