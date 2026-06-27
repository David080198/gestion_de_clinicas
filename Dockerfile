# ============================================================
# Dockerfile - MedCenter Premium Medical Tech
# Multi-stage build optimizado para produccion en Dokploy
#
# Stage 1: builder  -> instala dependencias en wheel
# Stage 2: runtime  -> imagen final minima, non-root
# ============================================================

# ---------- Stage 1: Builder ----------
FROM python:3.11-slim AS builder

# Metadatos
LABEL stage="builder"

# Evita archivos .pyc y buffer de stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100

# Directorio de trabajo del builder
WORKDIR /build

# Instalar dependencias del sistema para compilar psycopg2 y bcrypt
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar solo requirements para aprovechar cache de capas
COPY requirements.txt .

# Instalar dependencias en un directorio aislado (wheel)
RUN pip install --user --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --user --no-cache-dir -r requirements.txt


# ---------- Stage 2: Runtime ----------
FROM python:3.11-slim AS runtime

# Metadatos
LABEL org.opencontainers.image.title="MedCenter Premium" \
      org.opencontainers.image.description="Sistema de gestion de consultorios medicos multirrol" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.authors="MedCenter"

# Variables de entorno del runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FLASK_ENV=production \
    APP_PORT=5000 \
    PYTHONPATH="/app:/home/medcenter/.local/lib/python3.11/site-packages"

# Instalar solo runtime libs (sin build-essential -> imagen mas pequena)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Crear usuario non-root con home real para que Python encuentre site-packages
RUN groupadd -r medcenter && \
    useradd -r -g medcenter -d /home/medcenter -s /sbin/nologin medcenter && \
    mkdir -p /home/medcenter

# Copiar dependencias del builder
COPY --from=builder /root/.local /home/medcenter/.local
ENV PATH="/home/medcenter/.local/bin:${PATH}"

# Directorio de la aplicacion
WORKDIR /app

# Copiar codigo de la aplicacion
COPY --chown=medcenter:medcenter . /app/

# Asegurar permisos del entrypoint y directorios
RUN chmod +x /app/docker-entrypoint.sh && \
    mkdir -p /app/migrations/versions /app/logs /tmp/gunicorn && \
    chown -R medcenter:medcenter /app /home/medcenter /tmp/gunicorn

# Cambiar a usuario non-root
USER medcenter

# Exponer puerto interno (Dokploy/Traefik enruta via labels)
EXPOSE 5000

# Healthcheck: verifica que la app responde
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${APP_PORT}/health || exit 1

# Punto de entrada: wait-for-db + migraciones + gunicorn
ENTRYPOINT ["/app/docker-entrypoint.sh"]
