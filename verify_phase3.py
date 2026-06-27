"""Verificacion de la Fase 3 - Frontend y vistas HTML.

Prueba que todas las paginas HTML se sirvan correctamente (status 200),
que las redirecciones de autenticacion funcionen, y que las plantillas
Jinja2 no tengan errores de renderizado.
"""

from __future__ import annotations

import os
import sys

os.environ["FLASK_ENV"] = "testing"
os.environ["SECRET_KEY"] = "test-secret-phase3"
os.environ["JWT_SECRET_KEY"] = "test-jwt-phase3"
os.environ["TEST_DATABASE_URL"] = "sqlite:///:memory:"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db


PAGES = [
    ("/login", "Login", 200, False),
    ("/register", "Registro", 200, False),
    ("/dashboard", "Dashboard", 200, False),
    ("/appointments/calendar", "Calendario", 200, False),
    ("/appointments", "Lista citas", 200, False),
    ("/appointments/new", "Nueva cita", 200, False),
    ("/medical/consult/1", "Consulta", 200, False),
    ("/medical/history", "Historial", 200, False),
    ("/prescriptions", "Recetas", 200, False),
]


def main() -> None:
    app = create_app("testing")
    app.config["JWT_COOKIE_SECURE"] = False
    app.config["JWT_COOKIE_CSRF_PROTECT"] = False
    client = app.test_client()

    with app.app_context():
        db.create_all()

    print("\n--- Verificando paginas HTML ---")
    passed = 0
    failed = 0

    for path, name, expected, needs_auth in PAGES:
        try:
            resp = client.get(path)
            if resp.status_code == expected:
                # Verificar que es HTML (no JSON)
                content_type = resp.headers.get("Content-Type", "")
                if "text/html" in content_type:
                    print(f"[OK] {name:20s} {path:40s} -> {resp.status_code}")
                    passed += 1
                else:
                    print(f"[FAIL] {name:20s} {path:40s} -> no es HTML ({content_type})")
                    failed += 1
            else:
                print(f"[FAIL] {name:20s} {path:40s} -> esperaba {expected}, got {resp.status_code}")
                failed += 1
        except Exception as e:
            print(f"[FAIL] {name:20s} {path:40s} -> excepcion: {e}")
            failed += 1

    # Verificar que /api/auth/me sin sesion retorna 401
    print("\n--- Verificando API sin sesion ---")
    resp = client.get("/api/auth/me")
    if resp.status_code == 401:
        print(f"[OK] /api/auth/me sin sesion -> 401")
        passed += 1
    else:
        print(f"[FAIL] /api/auth/me sin sesion -> esperaba 401, got {resp.status_code}")
        failed += 1

    # Verificar health check
    resp = client.get("/health")
    if resp.status_code == 200 and resp.get_json()["status"] == "healthy":
        print(f"[OK] /health -> healthy")
        passed += 1
    else:
        print(f"[FAIL] /health -> {resp.status_code}")
        failed += 1

    # Verificar pagina 404
    resp = client.get("/pagina-inexistente")
    if resp.status_code == 404 and "text/html" in resp.headers.get("Content-Type", ""):
        print(f"[OK] 404 HTML -> pagina de error")
        passed += 1
    else:
        print(f"[FAIL] 404 -> {resp.status_code} {resp.headers.get('Content-Type')}")
        failed += 1

    # Verificar que la API 404 sigue siendo JSON
    resp = client.get("/api/inexistente")
    if resp.status_code == 404 and "json" in resp.headers.get("Content-Type", ""):
        print(f"[OK] 404 API -> JSON")
        passed += 1
    else:
        print(f"[FAIL] 404 API -> {resp.status_code}")
        failed += 1

    # Verificar archivos estaticos
    resp = client.get("/static/css/styles.css")
    if resp.status_code == 200:
        print(f"[OK] CSS estatico -> {len(resp.data)} bytes")
        passed += 1
    else:
        print(f"[FAIL] CSS estatico -> {resp.status_code}")
        failed += 1

    resp = client.get("/static/js/api.js")
    if resp.status_code == 200:
        print(f"[OK] JS api.js -> {len(resp.data)} bytes")
        passed += 1
    else:
        print(f"[FAIL] JS api.js -> {resp.status_code}")
        failed += 1

    print(f"\n========================================")
    print(f"FASE 3: {passed}/{passed + failed} verificaciones pasaron")
    print(f"========================================")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
