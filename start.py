"""Démarrage en un clic : installe ce qu'il faut au premier lancement, puis ouvre Jobbys.

Appelé par Jobbys.bat (Windows) ou Jobbys.command (Mac). N'utilise que la
bibliothèque standard de Python, puisqu'il tourne avant toute installation.
"""

import hashlib
import os
import shutil
import socket
import subprocess
import sys
import venv
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
STAMP = VENV / ".jobbys-installed"
URL = "http://localhost:8000"
WINDOWS = os.name == "nt"


def say(text: str) -> None:
    print(f"[Jobbys] {text}", flush=True)


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if WINDOWS else "bin/python")


def already_running() -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", 8000)) == 0


def update_code() -> None:
    if (ROOT / ".git").exists() and shutil.which("git"):
        say("Recherche de mises à jour...")
        subprocess.run(["git", "pull", "--ff-only", "-q"], cwd=ROOT, check=False)


def install() -> None:
    requirements = (ROOT / "requirements.txt").read_bytes()
    wanted = hashlib.sha256(requirements).hexdigest()
    if STAMP.exists() and STAMP.read_text() == wanted:
        return
    if not venv_python().exists():
        say("Première installation, ça prend quelques minutes...")
        venv.create(VENV, with_pip=True)
    python = str(venv_python())
    subprocess.run([python, "-m", "pip", "install", "-q", "--upgrade", "pip"], check=True)
    subprocess.run([python, "-m", "pip", "install", "-q", "-r", str(ROOT / "requirements.txt")], check=True)
    say("Installation du navigateur qui remplit les formulaires...")
    subprocess.run([python, "-m", "playwright", "install", "chromium"], check=True)
    STAMP.write_text(wanted)


def desktop_shortcut() -> None:
    """Crée un raccourci « Jobbys » sur le bureau Windows, une seule fois."""
    if not WINDOWS:
        return
    marker = VENV / ".jobbys-shortcut"
    if marker.exists():
        return
    target = str(ROOT / "Jobbys.bat").replace("'", "''")
    folder = str(ROOT).replace("'", "''")
    script = (
        "$d=[Environment]::GetFolderPath('Desktop');"
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut(\"$d\\Jobbys.lnk\");"
        f"$s.TargetPath='{target}';$s.WorkingDirectory='{folder}';$s.Save()"
    )
    result = subprocess.run(["powershell", "-NoProfile", "-Command", script], check=False)
    if result.returncode == 0:
        say("Raccourci « Jobbys » ajouté sur ton bureau.")
        marker.write_text("ok")


def main() -> None:
    if sys.version_info < (3, 11):
        say(f"Python 3.11 ou plus récent est nécessaire (tu as {sys.version.split()[0]}).")
        say("Télécharge-le sur https://www.python.org/downloads/ puis relance Jobbys.")
        return
    if already_running():
        say("Jobbys tourne déjà, j'ouvre la page.")
        webbrowser.open(URL)
        return
    update_code()
    install()
    desktop_shortcut()
    say(f"Jobbys démarre sur {URL}. Laisse cette fenêtre ouverte ; ferme-la pour arrêter Jobbys.")
    subprocess.run([str(venv_python()), "-m", "app"], cwd=ROOT, check=False)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError:
        say("L'installation a échoué. Vérifie ta connexion internet et relance Jobbys.")
        try:
            input("Appuie sur Entrée pour fermer.")
        except EOFError:
            pass
