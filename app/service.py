"""Ce que fait Jobbys en arrière-plan : collecter, analyser, candidater."""

import json
import logging
import subprocess
import sys
import tempfile
import threading
import webbrowser
from concurrent.futures import ThreadPoolExecutor

from . import llm, sources
from .apply import channel_for
from .apply import email as email_apply
from .config import ROOT, load_profile, settings
from .db import Database

log = logging.getLogger("jobbys")


class Jobbys:
    def __init__(self, db: Database):
        self.db = db
        self.fetch_state = {"running": False, "errors": [], "new": 0, "seen": 0}
        self._analysis_lock = threading.Lock()

    # --- collecte -----------------------------------------------------------

    def fetch(self) -> None:
        if self.fetch_state["running"]:
            return
        self.fetch_state = {"running": True, "errors": [], "new": 0, "seen": 0}
        try:
            profile = load_profile()
            keywords = profile.mots_cles or [""]
            places = profile.lieux or [""]
            active = [s for s in sources.ALL if s.enabled()]
            if not active:
                self.fetch_state["errors"].append(
                    "Aucune source configurée : renseigne au moins une clé API dans .env."
                )
            for source in active:
                for keyword in keywords:
                    for place in places:
                        try:
                            for raw in source.search(keyword, place):
                                _, is_new = self.db.ingest(raw)
                                self.fetch_state["seen"] += 1
                                self.fetch_state["new"] += int(is_new)
                        except Exception as exc:  # une source en panne ne bloque pas les autres
                            log.exception("Source %s", source.NAME)
                            self.fetch_state["errors"].append(f"{source.NAME} : {exc}")
        finally:
            self.fetch_state["running"] = False
        self.analyze_pending()

    def analyze_pending(self) -> None:
        if not self._analysis_lock.acquire(blocking=False):
            return
        try:
            profile = load_profile()
            offers = self.db.offers_to_analyze()

            def work(offer):
                try:
                    self.db.save_analysis(offer["id"], llm.analyze_offer(offer, profile))
                except Exception as exc:
                    log.exception("Analyse de l'offre %s", offer["id"])
                    self.db.save_analysis_error(offer["id"], str(exc))

            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(work, offers))
        finally:
            self._analysis_lock.release()

    # --- candidature --------------------------------------------------------

    def like(self, offer_id: int) -> int:
        offer = self.db.get_offer(offer_id)
        self.db.set_status(offer_id, "liked")
        channel = channel_for(offer)
        app_id = self.db.create_application(offer_id, channel)
        threading.Thread(target=self.apply, args=(app_id, offer, channel), daemon=True).start()
        return app_id

    def apply(self, app_id: int, offer: dict, channel: str) -> None:
        profile = load_profile()
        try:
            letter = llm.write_letter(offer, profile, channel)
            self.db.update_application(app_id, message=letter.message)
            if channel == "email":
                if settings.email_dry_run:
                    self.db.update_application(
                        app_id, status="dry_run",
                        detail=f"Email prêt pour {offer['apply_email']} (non envoyé : mode test)",
                    )
                else:
                    if not (profile.prenom and profile.nom and profile.cv_path):
                        raise RuntimeError("Ajoute ton prénom, ton nom et ton CV dans Réglages avant d'envoyer.")
                    status, detail = email_apply.deliver(
                        offer["apply_email"], letter.objet, letter.message, profile
                    )
                    self.db.update_application(app_id, status=status, detail=detail)
            elif channel == "form":
                self.open_form(app_id, offer, letter.message, profile)
            else:
                webbrowser.open(offer.get("apply_url") or offer["url"])
                self.db.update_application(
                    app_id, status="to_do",
                    detail="Offre ouverte dans ton navigateur : copie le message et postule sur LinkedIn.",
                )
        except Exception as exc:
            log.exception("Candidature %s", app_id)
            self.db.update_application(app_id, status="error", detail=str(exc))

    def open_form(self, app_id: int, offer: dict, message: str, profile) -> None:
        job = {
            "url": offer.get("apply_url") or offer["url"],
            "message": message,
            "cv_path": str(profile.cv_path) if profile.cv_path else "",
            "browser_profile_dir": str(settings.browser_profile_dir),
            "profile": {
                "prenom": profile.prenom,
                "nom": profile.nom,
                "nom_complet": f"{profile.prenom} {profile.nom}".strip(),
                "email": profile.email,
                "telephone": profile.telephone,
                "ville": profile.ville,
                "linkedin": profile.linkedin,
            },
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(job, f, ensure_ascii=False)
        proc = subprocess.Popen(
            [sys.executable, "-m", "app.apply.form", f.name],
            cwd=ROOT, stdout=subprocess.PIPE, text=True,
        )
        line = proc.stdout.readline()  # le script écrit une ligne dès que le remplissage est fini
        try:
            filled = json.loads(line).get("filled", [])
        except (json.JSONDecodeError, AttributeError):
            self.db.update_application(
                app_id, status="error", detail="Le navigateur n'a pas pu ouvrir le formulaire."
            )
            return
        if filled:
            detail = "Formulaire prérempli (" + ", ".join(filled) + ") : vérifie et clique sur Envoyer."
        else:
            detail = "Page ouverte, mais aucun champ reconnu : colle le message toi-même."
        self.db.update_application(app_id, status="prefilled", detail=detail)
