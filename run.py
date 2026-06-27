"""Punto de entrada de la aplicacion para desarrollo local.

En produccion se ejecuta mediante gunicorn (ver Dockerfile):
    gunicorn -w 4 -b 0.0.0.0:5000 "run:app"
"""

from __future__ import annotations

import os

from app import create_app

app = create_app(os.environ.get("FLASK_ENV", "production"))


if __name__ == "__main__":
    port: int = int(os.environ.get("APP_PORT", 5000))
    debug: bool = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
