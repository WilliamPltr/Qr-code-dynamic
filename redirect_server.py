from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

from flask import Flask, redirect, Response

app = Flask(__name__)


def load_current_target(config_path: Path) -> str:
    """Lit le fichier JSON de configuration et retourne l'URL cible.

    Ne lève pas d'écriture disque. En cas d'erreur, retourne une URL sûre.
    """
    try:
        with config_path.open("r", encoding="utf-8") as f:
            data: Dict[str, Any] = json.load(f)
        target = str(data.get("current_target", "")).strip()
        if not target:
            raise ValueError("Champ 'current_target' manquant ou vide")
        return target
    except Exception:
        # Fallback sûr: page neutre locale
        return "https://www.opack.fr/"


@app.get("/")
def root() -> Response:
    return Response("OK", mimetype="text/plain")


@app.get("/x")
def redirect_x() -> Response:
    config_path = Path(__file__).with_name("redirect.json")
    target = load_current_target(config_path)
    return redirect(target, code=302)


if __name__ == "__main__":
    port_str = os.getenv("PORT", "8000")
    try:
        port = int(port_str)
    except ValueError:
        port = 8000
    app.run(host="0.0.0.0", port=port)
