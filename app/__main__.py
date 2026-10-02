import logging
import threading
import webbrowser

import uvicorn

from .main import create_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

if __name__ == "__main__":
    print("Jobbys tourne sur http://localhost:8000 (Ctrl+C pour arrêter)")
    # On ouvre la page une fois le serveur lancé.
    threading.Timer(1.5, webbrowser.open, args=["http://localhost:8000"]).start()
    uvicorn.run(create_app(), host="127.0.0.1", port=8000)
