# MedCenter Premium - Guia de Despliegue en Dokploy

Sistema de gestion integral de consultorios medicos multirrol.

## Stack

- **Backend:** Python 3.11 + Flask 3.0 + SQLAlchemy 2.0 + JWT
- **Base de datos:** PostgreSQL 16
- **Frontend:** Tailwind CSS + JavaScript vanilla
- **Servidor:** Gunicorn (WSGI)
- **Proxy/SSL:** Traefik (interno de Dokploy)
- **Contenedor:** Docker + Docker Compose

---

## Despliegue en Dokploy

### 1. Preparar el repositorio

Sube el proyecto a tu repositorio Git (GitHub/GitLab). Dokploy clonara
el repo y leera el `docker-compose.yml` automaticamente.

### 2. Crear el servicio en Dokploy

1. Entra al panel de Dokploy.
2. **New Service** > **Docker Compose** (o **Compose**).
3. Selecciona tu repositorio o pega el contenido del `docker-compose.yml`.
4. Dokploy autodetectara los servicios `app` y `db`.

### 3. Configurar variables de entorno

En el panel de Dokploy, en la seccion **Environment Variables** del servicio,
define al menos:

| Variable | Valor | Notas |
|----------|-------|-------|
| `SECRET_KEY` | cadena aleatoria de 64 chars | **Obligatorio** |
| `JWT_SECRET_KEY` | cadena aleatoria | **Obligatorio** |
| `POSTGRES_PASSWORD` | password segura | **Obligatorio** |
| `DOMAIN` | `medcenter.tudominio.com` | Dominio asignado por Dokploy |
| `JWT_COOKIE_SECURE` | `true` | Cookies seguras tras HTTPS |
| `SEED_DEMO_DATA` | `0` o `1` | `1` para cargar datos demo |

Dokploy inyecta estas variables de forma segura (no quedan en el repo).

### 4. Red de Dokploy (Traefik)

Dokploy gestiona Traefik y crea una red Docker llamada `dokploy-network`
por defecto. El `docker-compose.yml` referencia esta red como `external`.

Si el nombre de tu red de Dokploy difiere, ajusta la variable:

```
DOKPLOY_NETWORK=tu-red-dokploy
```

### 5. Desplegar

1. Click en **Deploy** en el panel de Dokploy.
2. Dokploy construira la imagen (Dockerfile multi-stage) y levantara
   los servicios `app` y `db`.
3. El `docker-entrypoint.sh` espera a PostgreSQL, ejecuta migraciones
   y arranca Gunicorn automaticamente.
4. Traefik generara el certificado SSL (Let's Encrypt) y enrutara
   el trafico HTTPS al contenedor `app` en el puerto 5000.

### 6. Verificar

- Visita `https://medcenter.tudominio.com/health` -> `{"status":"healthy"}`
- Visita `https://medcenter.tudominio.com/login` -> pagina de inicio de sesion

---

## Estructura de servicios

```
                    Internet
                       |
                  [Traefik]  (Dokploy)
                   / SSL \
                      |
            +------------------+
            |   app (Flask)   |  puerto 5000 (interno)
            |   Gunicorn      |
            +------------------+
                      |
            +------------------+
            |   db (Postgres) |  puerto 5432 (interno)
            |   volumen:      |
            |   medcenter-pg  |
            +------------------+
```

- La app **no publica puertos** al host. Traefik enruta via labels.
- PostgreSQL **no es accesible** externamente (solo en la red interna).
- Los datos de PostgreSQL persisten en el volumen `medcenter-pgdata`.

---

## Comandos utiles

### Desarrollo local sin Docker

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
export FLASK_ENV=development
export DATABASE_URL=postgresql://user:pass@localhost:5432/clinic_db
flask db upgrade
flask run
```

### Construccion y arranque local con Docker

```bash
# Construir y levantar
docker compose up -d --build

# Ver logs
docker compose logs -f app

# Ejecutar migraciones manualmente
docker compose exec app flask db upgrade

# Crear usuario admin desde el shell
docker compose exec app flask shell
```

### Verificacion de fases

```bash
python verify_phase1.py   # Modelos de datos
python verify_phase2.py   # Backend API + endpoints
python verify_phase3.py   # Frontend HTML + estaticos
```

---

## Seguridad

- Las contrasenas se cifran con **Werkzeug PBKDF2-SHA256**.
- Los JWT viajan en **cookies HttpOnly** (anti-XSS).
- **CSRF protection** habilitada por defecto en produccion.
- El contenedor corre como usuario **non-root** (`medcenter`).
- PostgreSQL **no se expone** al host.
- Traefik aplica **HSTS** y redireccion HTTPS automatica.

---

## Resolucion de problemas

### PostgreSQL no conecta
- Verifica que `POSTGRES_PASSWORD` coincida en `app` y `db`.
- Revisa los logs: `docker compose logs db`.
- El entrypoint espera hasta 60s antes de fallar.

### Traefik no enruta
- Confirma que `DOMAIN` coincide con el dominio configurado en Dokploy.
- Verifica que la red `dokploy-network` exista: `docker network ls`.
- Revisa los labels de Traefik en `docker-compose.yml`.

### Migraciones fallan
- Si es primer despliegue, el entrypoint usa `flask init-db` como fallback.
- Para reiniciar la BD: `docker compose down -v` (borra el volumen).
- Verifica permisos del usuario `medcenter` sobre `/app/migrations`.

### Cookies JWT no funcionan
- En produccion, `JWT_COOKIE_SECURE=true` requiere HTTPS.
- Si pruebas sin HTTPS, setea `JWT_COOKIE_SECURE=false`.
- Detras de Traefik, el esquema es `https` por defecto.
