"""Configuracion de Gunicorn para produccion.

Optimizada para Dokploy / Docker:
    - Workers basados en nucleos de CPU (2-4 x cores)
    - Timeout generoso para migraciones y generacion de PDFs
    - Logging estructurado a stdout (Dokploy los captura)
    - Graceful shutdown para no cortar requests en curso
"""

from __future__ import annotations

import multiprocessing
import os

# Numero de workers: (2 x CPU) + 1, con tope para contenedores pequenos
cpu_count: int = multiprocessing.cpu_count()
workers: int = int(os.environ.get("GUNICORN_WORKERS", min(4, (2 * cpu_count) + 1)))

# Workers por tipo
worker_class: str = "sync"  # sync es seguro para Flask + SQLAlchemy
threads: int = int(os.environ.get("GUNICORN_THREADS", 2))

# Timeout: generoso para PDFs y migraciones
timeout: int = int(os.environ.get("GUNICORN_TIMEOUT", 120))
graceful_timeout: int = 30
keepalive: int = 5

# Bind
bind: str = "0.0.0.0:" + str(os.environ.get("APP_PORT", "5000"))

# Logging
accesslog: str = "-"  # stdout
errorlog: str = "-"   # stderr
loglevel: str = os.environ.get("GUNICORN_LOG_LEVEL", "info")
access_log_format: str = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sμs'

# Seguridad y rendimiento
limit_request_line: int = 8190
limit_request_fields: int = 100
limit_request_field_size: int = 8190

# Preload para compartir conexiones entre workers (reduce memoria)
preload_app: bool = True
max_requests: int = 1000          # reinicia workers tras N requests (memory leaks)
max_requests_jitter: int = 50     # aleatoriza para evitar reinicios sincronos

# Graceful shutdown
daemon: bool = False
pidfile: str = "/tmp/gunicorn.pid"
tmp_upload_dir: str = "/tmp"
