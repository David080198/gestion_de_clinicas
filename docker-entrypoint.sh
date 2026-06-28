#!/bin/sh
# ============================================================
# docker-entrypoint.sh
# Punto de entrada del contenedor Flask en produccion (Dokploy).
#
# Tareas:
#   1. Espera a que PostgreSQL este listo.
#   2. Construye DATABASE_URL si no fue inyectada.
#   3. Ejecuta migraciones de Alembic (flask db upgrade).
#   4. Opcionalmente aplica seed de datos demo (SEED_DEMO_DATA=1).
#   5. Arranca Gunicorn.
#
# Seguridad:
#   - En produccion, si `flask db upgrade` falla, el contenedor falla.
#   - El fallback `flask init-db` SOLO se activa si
#     ALLOW_INIT_DB_FALLBACK=1 (util en primer despliegue local).
# ============================================================
set -e

echo "============================================"
echo "  MedCenter Premium - Iniciando contenedor"
echo "============================================"

# ------------------------------------------------------------
# 1. Construir DATABASE_URL si no existe
# ------------------------------------------------------------
if [ -z "${DATABASE_URL}" ] && [ -n "${POSTGRES_HOST}" ]; then
    export DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
    echo "[entrypoint] DATABASE_URL construida desde variables POSTGRES_*"
fi

if [ -z "${DATABASE_URL}" ]; then
    echo "[entrypoint] ERROR: DATABASE_URL no definida. Define DATABASE_URL o POSTGRES_* en el entorno."
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
# 3. Reset de base de datos (si RESET_DATABASE=1)
# ------------------------------------------------------------
if [ "${RESET_DATABASE}" = "1" ]; then
    echo "[entrypoint] ⚠️  RESET_DATABASE=1: Reseteando base de datos..."
    python -c "
import psycopg2
import os
from urllib.parse import urlparse

db_url = os.environ.get('DATABASE_URL')
if db_url:
    # Parsear DATABASE_URL para obtener credenciales
    try:
        # Conectar para resetear
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()
        print('[*] Eliminando schema public...')
        cur.execute('DROP SCHEMA IF EXISTS public CASCADE;')
        print('[+] Schema eliminado')
        print('[*] Recreando schema public...')
        cur.execute('CREATE SCHEMA public;')
        cur.execute('GRANT ALL ON SCHEMA public TO postgres;')
        cur.execute('GRANT ALL ON SCHEMA public TO public;')
        print('[+] Schema recreado - BD reseteada')
        cur.close()
        conn.close()
    except Exception as e:
        print(f'ERROR durante reset: {e}')
        exit(1)
"
    echo "[entrypoint] ✓ Base de datos reseteada exitosamente."
    echo "[entrypoint] ⚠️  IMPORTANTE: Cambia RESET_DATABASE=0 y reinicia para aplicar migraciones."
fi

# ------------------------------------------------------------
# 4. Ejecutar migraciones de Alembic
# ------------------------------------------------------------
echo "[entrypoint] Aplicando migraciones de base de datos..."
if flask db upgrade; then
    echo "[entrypoint] Migraciones aplicadas correctamente."
else
    echo "[entrypoint] ERROR: flask db upgrade fallo."
    if [ "${ALLOW_INIT_DB_FALLBACK}" = "1" ]; then
        echo "[entrypoint] ALLOW_INIT_DB_FALLBACK=1: creando tablas directamente..."
        flask init-db
        echo "[entrypoint] Tablas creadas."
    else
        echo "[entrypoint] Para usar el fallback init-db, define ALLOW_INIT_DB_FALLBACK=1."
        exit 1
    fi
fi

# ------------------------------------------------------------
# 5. Seed opcional (solo si SEED_DEMO_DATA=1)
# ------------------------------------------------------------
if [ "${SEED_DEMO_DATA}" = "1" ]; then
    echo "[entrypoint] Aplicando datos demo..."
    flask seed
    echo "[entrypoint] Datos demo aplicados."
fi

# ------------------------------------------------------------
# 6. Arrancar Gunicorn
# -----------------------------------------------
echo "[entrypoint] Arrancando Gunicorn en el puerto ${APP_PORT:-5000}..."
exec gunicorn -c gunicorn.conf.py "wsgi:app"
