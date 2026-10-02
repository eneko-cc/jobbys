#!/bin/bash
# Double-clique sur ce fichier pour lancer Jobbys (Mac).
cd "$(dirname "$0")"
if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then
  python3 start.py
else
  echo "[Jobbys] Il faut Python 3.11 ou plus récent : https://www.python.org/downloads/"
  open "https://www.python.org/downloads/"
fi
read -n 1 -s -r -p "Appuie sur une touche pour fermer."
