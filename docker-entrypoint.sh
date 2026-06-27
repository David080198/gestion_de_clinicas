#!/bin/sh
# ============================================================
# docker-entrypoint.sh
# Punto de entrada del contenedor Flask en Dokploy.
#
# Tareas:
#   1. Espera a que PostgreSQL este listo (healthcheck).
#   2. Construye DATABASE_URL si no fue inyectada por Dokploy.
#   3. Ejecuta migraciones de Alembic (Flask-Migrate).
#   4. Opcionalmente aplica seed de datos demo.
#   5. Arranca Gunicorn con la configuracion de produccion.
# ============================================================
set -e

echo "============================================"
echo "  MedCenter Premium - Iniciando contenedor"
echo "============================================"

# ------------------------------------------------------------
# 1. Construir DATABASE_URL si no existe (compatibilidad Dokploy)
# ------------------------------------------------------------
if [ -z "${DATABASE_URL}" ] && [ -n "${POSTGRES_HOST}" ]; then
    export DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
    echo "[entrypoint] DATABASE_URL construida desde variables POSTGRES_*"
fi

if [ -z "${DATABASE_URL}" ]; then
    echo "[entrypoint] ERROR: DATABASE_URL no definida. Define DATABASE_URL o POSTGRES_* en Dokploy."
    exit 1
fi

# ------------------------------------------------------------
# 2. Esperar a que PostgreSQL este listo
# ------------------------------------------------------------
echo "[entrypoint] Esperando PostgreSQL en ${POSTGRES_HOST:-db}:${POSTGRES_PORT:-5432}..."

MAX_RETRIES=30
RETRY=0
until python -c "
import sys
import psycopg2
try:
    conn = psycopg2.connect(
        host='${POSTGRES_HOST:-db}',
        port='${POSTGRES_PORT:-5432}',
        dbname='${POSTGRES_DB:-clinic_db}',
        user='${POSTGRES_USER:-clinic_user}',
        password='${POSTGRES_PASSWORD:-clinic_password}',
        connect_timeout=3,
    )
    conn.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; do
    RETRY=$((RETRY + 1))
    if [ $RETRY -ge $MAX_RETRIES ]; then
        echo "[entrypoint] ERROR: PostgreSQL no disponible tras $MAX_RETRIES intentos."
        exit 1
    fi
    echo "[entrypoint] Reintentando ($RETRY/$MAX_RETRIES)..."
    sleep 2
done
echo "[entrypoint] PostgreSQL listo."

# ------------------------------------------------------------
# 3. Ejecutar migraciones (Flask-Migrate / Alembic)
# ------------------------------------------------------------
echo "[entrypoint] Aplicando migraciones de base de datos..."
flask db upgrade 2>/dev/null || {
    echo "[entrypoint] No hay migraciones o fallaron. Creando tablas directamente..."
    flask init-db
}
echo "[entrypoint] Base de datos lista."

# ------------------------------------------------------------
# 4. Seed opcional ( solo si SEED_DEMO_DATA=1 )
# ------------------------------------------------------------
if [ "${SEED_DEMO_DATA}" = "1" ]; then
    echo "[entrypoint] Aplicando datos demo..."
    flask seed 2>/dev/null || echo "[entrypoint] Seed omitido (pendiente Fase 2)."
fi

# ------------------------------------------------------------
# 5. Arrancar Gunicorn
# ------------------------------------------------------------
echo "[entrypoint] Arrancando Gunicorn en el puerto ${APP_PORT:-5000}..."
exec gunicorn -c gunicorn.conf.py "wsgi:app"
