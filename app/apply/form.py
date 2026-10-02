"""Préremplissage d'un formulaire de candidature dans un vrai navigateur.

Lancé dans un processus à part (python -m app.apply.form job.json) pour que la
fenêtre reste ouverte. Le navigateur garde ses cookies dans data/browser : si tu
te connectes une fois à Welcome to the Jungle ou HelloWork, tu le restes.
Ce script ne clique JAMAIS sur le bouton d'envoi.
"""

import json
import re
import sys

from playwright.sync_api import Frame, Page, sync_playwright

CDP_PORT = 9333

APPLY_BUTTON = re.compile(r"^\s*(postuler|je postule|candidater|apply|apply now|postuler maintenant)\s*$", re.I)

FIELDS = [
    # (clé du profil, motif sur name/id/placeholder/label, types d'input acceptés)
    ("prenom", r"pr[eé]nom|first.?name|given.?name|firstname", None),
    ("nom_complet", r"full.?name|nom complet|^\s*name\s*$|^name\b", None),
    ("nom", r"(?<!pr[eé])\bnom\b|last.?name|family.?name|surname|lastname", None),
    ("email", r"e-?mail|courriel", None),
    ("telephone", r"t[eé]l[eé]phone|\btel\b|phone|mobile|portable", None),
    ("ville", r"\bville\b|\bcity\b|localisation|location", None),
    ("linkedin", r"linkedin", None),
]
MESSAGE = re.compile(r"motivation|message|cover|lettre|pr[eé]sentation|commentaire|about", re.I)
CV = re.compile(r"\bcv\b|resume|résumé|curriculum", re.I)

BANNER_JS = """
(text) => {
  const el = document.createElement('div');
  el.textContent = text;
  el.style.cssText = 'position:fixed;z-index:2147483647;top:12px;left:50%;transform:translateX(-50%);'
    + 'background:#ff4f6d;color:#fff;font:600 15px system-ui;padding:12px 18px;border-radius:12px;'
    + 'box-shadow:0 6px 24px rgba(0,0,0,.25);max-width:90vw;text-align:center';
  el.onclick = () => el.remove();
  document.body.appendChild(el);
}
"""


def _describe(frame: Frame, handle) -> str:
    """Texte qui décrit un champ : name, id, placeholder, aria-label et label associé."""
    return frame.evaluate(
        """(el) => {
          const parts = [el.name, el.id, el.placeholder, el.getAttribute('aria-label'),
                         el.getAttribute('autocomplete'), el.getAttribute('data-testid')];
          if (el.id) { const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l) parts.push(l.innerText); }
          const wrap = el.closest('label'); if (wrap) parts.push(wrap.innerText);
          return parts.filter(Boolean).join(' ');
        }""",
        handle,
    )


def fill_frame(frame: Frame, job: dict) -> list[str]:
    profile = job["profile"]
    filled = []

    for handle in frame.query_selector_all("input:not([type=hidden]):not([type=file]):not([type=checkbox]):not([type=radio]):not([type=submit])"):
        try:
            if not handle.is_visible() or handle.input_value():
                continue
            desc = _describe(frame, handle)
            input_type = (handle.get_attribute("type") or "text").lower()
            for key, pattern, _ in FIELDS:
                value = profile.get(key)
                if not value:
                    continue
                if re.search(pattern, desc, re.I) or (key == "email" and input_type == "email") or (
                    key == "telephone" and input_type == "tel"
                ):
                    handle.fill(str(value))
                    filled.append(key)
                    break
        except Exception:
            continue

    textareas = [t for t in frame.query_selector_all("textarea") if t.is_visible()]
    target = next((t for t in textareas if MESSAGE.search(_describe(frame, t))), None)
    if target is None and textareas:
        target = textareas[0]
    if target is not None and not target.input_value():
        target.fill(job["message"])
        filled.append("message")

    cv_path = job.get("cv_path")
    if cv_path:
        files = frame.query_selector_all("input[type=file]")
        target = next((f for f in files if CV.search(_describe(frame, f))), files[0] if files else None)
        if target is not None:
            try:
                target.set_input_files(cv_path)
                filled.append("cv")
            except Exception:
                pass
    return filled


def click_apply_button(page: Page) -> None:
    for role in ("button", "link"):
        locator = page.get_by_role(role, name=APPLY_BUTTON)
        if locator.count():
            try:
                locator.first.click(timeout=3000)
                page.wait_for_timeout(2500)
                return
            except Exception:
                pass


def prefill(page: Page, job: dict) -> list[str]:
    page.goto(job["url"], wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(2000)
    click_apply_button(page)
    filled = []
    for frame in page.frames:
        filled += fill_frame(frame, job)
    note = (
        "Jobbys a prérempli ce formulaire. Vérifie, complète si besoin, puis clique sur Envoyer."
        if filled
        else "Jobbys n'a pas trouvé le formulaire : connecte-toi ou clique sur Postuler, le message est copiable dans Jobbys."
    )
    try:
        page.evaluate(BANNER_JS, note)
    except Exception:
        pass
    return filled


def main(job_path: str) -> None:
    with open(job_path, encoding="utf-8") as f:
        job = json.load(f)
    with sync_playwright() as p:
        try:
            # Une fenêtre Jobbys est déjà ouverte : on y ajoute un onglet.
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}", timeout=2000)
            page = browser.contexts[0].new_page()
            filled = prefill(page, job)
            print(json.dumps({"filled": filled}), flush=True)
            return
        except Exception:
            pass
        context = p.chromium.launch_persistent_context(
            job["browser_profile_dir"],
            headless=False,
            args=[f"--remote-debugging-port={CDP_PORT}"],
            no_viewport=True,
        )
        page = context.pages[0] if context.pages else context.new_page()
        filled = prefill(page, job)
        print(json.dumps({"filled": filled}), flush=True)
        # On garde le navigateur ouvert jusqu'à ce que tu le fermes.
        context.wait_for_event("close", timeout=0)


if __name__ == "__main__":
    main(sys.argv[1])
