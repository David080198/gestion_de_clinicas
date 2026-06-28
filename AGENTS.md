# Guia para Agentes de IA - MedCenter Premium

Este archivo contiene el contexto que necesitas para trabajar de forma segura y coherente en el proyecto MedCenter Premium.

## Vision general

MedCenter Premium es un sistema de gestion de clinicas medicas con multi-tenancy, suscripciones y roles (super-admin, admin, medico, recepcionista, paciente). Esta construido con Flask, SQLAlchemy 2.0, PostgreSQL y Docker.

## Reglas generales

1. **Nunca commitear secrets.** El archivo `.env` esta ignorado. Usa `.env.example` como plantilla.
2. **Siempre versionar migraciones de Alembic.** La carpeta `migrations/versions/` debe contener los archivos `.py` de migracion. Nunca agregar `migrations/versions/*.py` al `.gitignore`.
3. **Mantener la arquitectura modular.** La logica de negocio va en `app/services/`, los modelos en `app/models/`, los endpoints en `app/api/` y las plantillas en `app/templates/`.
4. **No romper las verificaciones existentes.** Antes de finalizar cambios, ejecuta los scripts `verify_phase*.py` o `pytest`.
5. **Mantener compatibilidad con Python 3.11**, que es la version del Dockerfile.
6. **Seguir el estilo de codigo existente:** type hints, docstrings en espanol, nombres de variables descriptivos.

## Estructura clave

```
app/
├── __init__.py          # Application factory y comandos CLI
├── config.py            # Configuracion por entorno (Base/Development/Testing/Production)
├── extensions.py        # db, migrate, jwt
├── exceptions.py        # Excepciones del dominio
├── models/              # Modelos SQLAlchemy + enums
├── api/                 # Blueprints Flask
├── services/            # Logica de negocio
├── schemas/             # Marshmallow schemas
├── templates/           # Jinja2
├── static/              # CSS/JS/imagenes
└── utils/               # Decoradores, tenant, paginacion
```

## Comandos esenciales

```bash
# Instalar dependencias
pip install -r requirements.txt

# Aplicar migraciones
flask db upgrade

# Crear nueva migracion
cd medical_clinic
flask db migrate -m "descripcion"

# Cargar datos demo
flask seed

# Ejecutar verificaciones
python verify_phase1.py
python verify_phase2.py
python verify_phase3.py
python verify_phase4.py
python verify_phase5.py
python verify_phase6.py

# Ejecutar tests
pytest
```

## Convenciones de modelos

- Todos los modelos heredan de `BaseModel` y `TimestampMixin`.
- Los enums se definen en `app/models/enums.py`, `app/models/tenant_enums.py` y `app/models/billing_enums.py`.
- Cada modelo expone `to_dict()` para serializacion.
- Los metodos `save()` y `delete()` estan en `BaseModel`.

## Convenciones de API

- Cada dominio tiene un blueprint en `app/api/`.
- Los endpoints JSON usan prefijo `/api/`.
- Las vistas HTML no usan prefijo `/api/`.
- El manejo de errores esta centralizado en `app/__init__.py`.

## Autenticacion y autorizacion

- JWT se almacena en cookies HttpOnly.
- CSRF esta habilitado en produccion.
- Roles: `admin`, `medico`, `recepcionista`, `paciente`.
- Un usuario con `clinic_id=None` y rol `admin` es super-admin.
- El aislamiento multi-tenant se hace filtrando por `clinic_id`.

## Multi-tenancy

- Cada recurso (usuarios, pacientes, citas, etc.) pertenece a una `Clinic` via `clinic_id`.
- Los super-admin no tienen `clinic_id`.
- Los admins de clinica solo pueden ver/crear recursos de su propia clinica.

## Docker y despliegue

- `Dockerfile` es multi-stage (builder + runtime) y usa usuario `medcenter`.
- `docker-compose.yml` esta optimizado para Dokploy/Traefik.
- `docker-compose.override.yml` publica el puerto `8090` en local y desactiva Traefik.
- El `docker-entrypoint.sh` ejecuta migraciones y arranca Gunicorn.

## Stripe

- La integracion con Stripe esta en `app/services/stripe_service.py` y `app/api/stripe.py`.
- Se soportan suscripciones recurrentes, checkout session, customer portal y webhooks.
- Los Price IDs de Stripe se configuran con variables de entorno (`STRIPE_PRICE_*`).
- Nunca versionar `STRIPE_SECRET_KEY` ni `STRIPE_WEBHOOK_SECRET`.
- Webhook endpoint: `POST /api/stripe/webhook`.

## Testing

- Preferir crear tests pytest en `tests/`.
- Los scripts `verify_phase*.py` funcionan como tests de integracion manuales.
- Para tests se usa la configuracion `TestingConfig` con SQLite en memoria.

## Variables de entorno importantes

Ver `.env.example` para la lista completa. Las mas importantes:

- `SECRET_KEY`, `JWT_SECRET_KEY`
- `DATABASE_URL`
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- `DOMAIN`
- `JWT_COOKIE_SECURE`, `JWT_COOKIE_CSRF_PROTECT`
- `SEED_DEMO_DATA`
- `ALLOW_INIT_DB_FALLBACK` (solo desarrollo)

## Que NO hacer

- No agregar secrets a `.env.example`.
- No borrar archivos de `migrations/versions/`.
- No usar `db.create_all()` en produccion; usar `flask db upgrade`.
- No exponer puertos de PostgreSQL en `docker-compose.yml`.
- No modificar la logica de negocio sin agregar/actualizar tests.

## Contacto y documentacion adicional

- `README.md`: guia general del proyecto.
- `DEPLOY.md`: guia de despliegue en Dokploy.
- `USUARIOS.md`: credenciales y datos de prueba.
- `MARKETING.md`: material de presentacion.
