import logging
import webbrowser

import uvicorn

from .main import create_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

if __name__ == "__main__":
    print("Jobbys tourne sur http://localhost:8000 (Ctrl+C pour arrêter)")
    webbrowser.open("http://localhost:8000")
    uvicorn.run(create_app(), host="127.0.0.1", port=8000)
