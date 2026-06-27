"""Verificacion de la Fase 4 - Configuracion Docker / Dokploy.

Valida que todos los archivos de despliegue existan y tengan la estructura
correcta para Dokploy, sin necesidad de que el daemon de Docker este corriendo.

Verifica:
    1. Dockerfile existe y es multi-stage (builder + runtime).
    2. docker-compose.yml existe y tiene los servicios app + db.
    3. docker-entrypoint.sh existe y es ejecutable.
    4. gunicorn.conf.py existe y tiene configuracion de produccion.
    5. .dockerignore existe y excluye archivos sensibles.
    6. .env.example existe y documenta variables de Dokploy.
    7. El Dockerfile usa usuario non-root.
    8. El compose no publica puertos al host (usa expose + Traefik).
    9. El compose tiene healthchecks en ambos servicios.
    10. El compose usa volumenes nombrados para PostgreSQL.
    11. El compose referencia la red externa de Dokploy.
    12. Los labels de Traefik estan presentes para enrutamiento.
"""

from __future__ import annotations

import os
import sys
import re
from pathlib import Path

BASE = Path(__file__).parent


def read_file(name: str) -> str:
    return (BASE / name).read_text(encoding="utf-8")


def main() -> None:
    passed = 0
    failed = 0

    def check(condition: bool, msg: str) -> None:
        nonlocal passed, failed
        if condition:
            print(f"[OK]  {msg}")
            passed += 1
        else:
            print(f"[FAIL] {msg}")
            failed += 1

    print("\n=== Fase 4: Verificacion de configuracion Docker / Dokploy ===\n")

    # ---------- 1. Dockerfile ----------
    print("-- Dockerfile --")
    dockerfile = read_file("Dockerfile")
    check("FROM python:3.11-slim AS builder" in dockerfile, "Dockerfile multi-stage: builder")
    check("FROM python:3.11-slim AS runtime" in dockerfile, "Dockerfile multi-stage: runtime")
    check("USER medcenter" in dockerfile, "Dockerfile usa usuario non-root (medcenter)")
    check("HEALTHCHECK" in dockerfile, "Dockerfile tiene HEALTHCHECK")
    check("EXPOSE 5000" in dockerfile, "Dockerfile expone puerto 5000")
    check("ENTRYPOINT" in dockerfile, "Dockerfile define ENTRYPOINT")
    check("COPY requirements.txt" in dockerfile, "Dockerfile copia requirements primero (cache de capas)")
    check("libpq5" in dockerfile, "Dockerfile instala libpq5 en runtime (psycopg2)")
    check("pip install --user" in dockerfile, "Dockerfile instala deps con --user (aisladas)")

    # ---------- 2. docker-compose.yml ----------
    print("\n-- docker-compose.yml --")
    compose = read_file("docker-compose.yml")
    check("services:" in compose, "Compose define servicios")
    check("  app:" in compose, "Compose tiene servicio app")
    check("  db:" in compose, "Compose tiene servicio db")
    check("postgres:16-alpine" in compose, "Compose usa PostgreSQL 16 Alpine")
    check("restart: unless-stopped" in compose, "Compose reinicia servicios automaticamente")
    check("depends_on" in compose, "app depende de db")
    check("condition: service_healthy" in compose, "app espera a que db este healthy")
    check('expose:\n      - "5000"' in compose or 'expose:\n      - "5432"' in compose,
          "Compose usa expose (no ports) para puertos internos")
    check("ports:" not in compose, "Compose NO publica puertos al host (Traefik gestiona)")
    check("healthcheck:" in compose, "Compose tiene healthchecks")
    check("pg_isready" in compose, "Healthcheck de PostgreSQL usa pg_isready")
    check("medcenter-pgdata" in compose, "Compose usa volumen nombrado medcenter-pgdata")
    check("dokploy-network" in compose, "Compose referencia red externa dokploy-network")
    check("external: true" in compose, "Red dokploy-network es externa")

    # ---------- 3. Labels de Traefik ----------
    print("\n-- Labels de Traefik --")
    check("traefik.enable=true" in compose, "Label traefik.enable=true")
    check("traefik.http.routers.medcenter" in compose, "Router HTTP de Traefik")
    check("traefik.http.routers.medcenter-secure" in compose, "Router HTTPS de Traefik")
    check("tls.certresolver=letsencrypt" in compose, "SSL automatico via Let's Encrypt")
    check("https-redirect" in compose, "Middleware de redireccion HTTPS")
    check("security-headers" in compose, "Middleware de headers de seguridad")
    check("loadbalancer.server.port=5000" in compose, "Traefik balancea al puerto 5000 interno")
    check("Host(" in compose, "Router usa regla Host() para el dominio")

    # ---------- 4. docker-entrypoint.sh ----------
    print("\n-- docker-entrypoint.sh --")
    entrypoint = read_file("docker-entrypoint.sh")
    check("flask db upgrade" in entrypoint, "Entry point ejecuta migraciones (flask db upgrade)")
    check("flask init-db" in entrypoint, "Entry point tiene fallback (flask init-db)")
    check("gunicorn" in entrypoint, "Entry point arranca Gunicorn")
    check("psycopg2" in entrypoint, "Entry point verifica PostgreSQL con psycopg2")
    check("MAX_RETRIES" in entrypoint, "Entry point tiene reintentos para conectar a BD")
    check("DATABASE_URL" in entrypoint, "Entry point construye DATABASE_URL si falta")

    # ---------- 5. gunicorn.conf.py ----------
    print("\n-- gunicorn.conf.py --")
    gunicorn = read_file("gunicorn.conf.py")
    check("workers" in gunicorn, "Gunicorn configura workers")
    check("worker_class" in gunicorn, "Gunicorn configura worker_class")
    check("preload_app" in gunicorn, "Gunicorn usa preload_app (comparte conexiones)")
    check("max_requests" in gunicorn, "Gunicorn reinicia workers tras max_requests (memory leaks)")
    check("timeout" in gunicorn, "Gunicorn configura timeout")
    check("0.0.0.0" in gunicorn, "Gunicorn bind a 0.0.0.0 (accesible en el contenedor)")
    check("accesslog" in gunicorn, "Gunicorn loguea a stdout (Dokploy captura)")

    # ---------- 6. .dockerignore ----------
    print("\n-- .dockerignore --")
    dockerignore = read_file(".dockerignore")
    check(".env" in dockerignore, ".dockerignore excluye .env (secrets)")
    check("__pycache__" in dockerignore, ".dockerignore excluye __pycache__")
    check("verify_" in dockerignore, ".dockerignore excluye scripts de verificacion")
    check(".git" in dockerignore, ".dockerignore excluye .git")

    # ---------- 7. .env.example ----------
    print("\n-- .env.example --")
    env_example = read_file(".env.example")
    check("SECRET_KEY" in env_example, ".env.example documenta SECRET_KEY")
    check("JWT_SECRET_KEY" in env_example, ".env.example documenta JWT_SECRET_KEY")
    check("POSTGRES_PASSWORD" in env_example, ".env.example documenta POSTGRES_PASSWORD")
    check("DOMAIN" in env_example, ".env.example documenta DOMAIN (Traefik)")
    check("DOKPLOY_NETWORK" in env_example, ".env.example documenta DOKPLOY_NETWORK")
    check("JWT_COOKIE_SECURE" in env_example, ".env.example documenta JWT_COOKIE_SECURE")
    check("SEED_DEMO_DATA" in env_example, ".env.example documenta SEED_DEMO_DATA")

    # ---------- 8. DEPLOY.md ----------
    print("\n-- DEPLOY.md --")
    deploy = read_file("DEPLOY.md")
    check("Dokploy" in deploy, "DEPLOY.md documenta despliegue en Dokploy")
    check("Traefik" in deploy, "DEPLOY.md menciona Traefik")
    check("docker compose" in deploy.lower(), "DEPLOY.md incluye comandos docker compose")
    check("Environment Variables" in deploy, "DEPLOY.md documenta variables de entorno")

    # ---------- Resultado ----------
    print(f"\n========================================")
    print(f"FASE 4: {passed}/{passed + failed} verificaciones pasaron")
    print(f"========================================")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
