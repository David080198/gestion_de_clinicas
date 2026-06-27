"""Punto de entrada WSGI para produccion (gunicorn).

Uso en el contenedor Docker (Dokploy):
    gunicorn -w 4 -b 0.0.0.0:5000 --access-logfile - "wsgi:app"
"""

from __future__ import annotations

import os

from app import create_app

app = create_app(os.environ.get("FLASK_ENV", "production"))
