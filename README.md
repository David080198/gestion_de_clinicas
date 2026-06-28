# MedCenter Premium

Sistema de gestion integral para clinicas y consultorios medicos multirrol.

## Stack tecnologico

- **Backend:** Python 3.11 + Flask 3.0 + SQLAlchemy 2.0
- **Base de datos:** PostgreSQL 16
- **Autenticacion:** JWT en cookies HttpOnly + CSRF
- **Frontend:** Tailwind CSS + JavaScript vanilla (Jinja2)
- **Servidor WSGI:** Gunicorn
- **Pasarela de pagos:** Stripe (suscripciones y webhooks)
- **Contenedores:** Docker + Docker Compose
- **Despliegue recomendado:** Dokploy + Traefik + SSL automatico

## Caracteristicas principales

- 4 roles: Super-admin, Admin, Medico, Recepcionista y Paciente
- Agendamiento de citas con control de colisiones
- Expedientes clinicos electronicos inmutables
- Recetas medicas electronicas con descarga PDF
- Dashboard con metricas por rol
- Multi-tenancy (multiples clinicas aisladas)
- Sistema de suscripciones con facturacion y pagos
- Webhook de pasarelas de pago

## Requisitos previos

- Python 3.11+
- PostgreSQL 16 (o Docker para levantar todo)
- Git

## Instalacion local (sin Docker)

1. Clonar el repositorio e ingresar al directorio.
2. Copiar variables de entorno:

   ```bash
   cp .env.example .env
   ```

3. Crear un entorno virtual e instalar dependencias:

   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS/Linux
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. Crear la base de datos PostgreSQL `clinic_db` y un usuario.
5. Actualizar `DATABASE_URL` en `.env`.
6. Aplicar migraciones:

   ```bash
   flask db upgrade
   ```

7. (Opcional) Cargar datos demo:

   ```bash
   flask seed
   ```

8. Iniciar la aplicacion:

   ```bash
   python run.py
   ```

La app estara disponible en `http://localhost:5000`.

## Desarrollo con Docker Compose

```bash
# Copiar variables de entorno
# En Windows usar: copy .env.example .env
cp .env.example .env

# Levantar app + PostgreSQL (puerto 8090 mapeado al host)
docker compose up -d --build

# Ver logs
docker compose logs -f app

# Ejecutar migraciones manualmente
docker compose exec app flask db upgrade

# Cargar datos demo
docker compose exec app flask seed
```

Accede a `http://localhost:8090`.

## Despliegue en Dokploy

Ver la guia completa en [`DEPLOY.md`](DEPLOY.md).

Resumen rapido:

1. Subir el repositorio a GitHub/GitLab.
2. En Dokploy crear un servicio tipo **Docker Compose**.
3. Configurar las variables de entorno obligatorias:
   - `SECRET_KEY`
   - `JWT_SECRET_KEY`
   - `POSTGRES_PASSWORD`
   - `DOMAIN`
4. Desplegar. Dokploy/Traefik gestionan SSL y el enrutamiento.

## Configuracion de Stripe

Para cobrar suscripciones con Stripe:

1. Crear cuenta en [Stripe](https://stripe.com).
2. Crear productos y precios recurrentes en el dashboard.
3. Configurar el webhook apuntando a `https://tudominio.com/api/stripe/webhook`.
4. Copiar las variables en `.env`:

```bash
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_STARTER_MONTHLY=price_...
STRIPE_PRICE_STARTER_YEARLY=price_...
STRIPE_PRICE_PROFESSIONAL_MONTHLY=price_...
STRIPE_PRICE_PROFESSIONAL_YEARLY=price_...
STRIPE_PRICE_CLINIC_MONTHLY=price_...
STRIPE_PRICE_CLINIC_YEARLY=price_...
```

Eventos de webhook soportados:

- `checkout.session.completed`
- `invoice.payment_succeeded`
- `invoice.payment_failed`
- `customer.subscription.deleted`

Endpoints de Stripe:

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| GET | `/api/stripe/config` | Publishable key |
| POST | `/api/stripe/checkout-session` | Crear sesion de checkout |
| POST | `/api/stripe/customer-portal` | Portal de gestion de pago |
| POST | `/api/stripe/webhook` | Webhook de Stripe |

## Variables de entorno principales

| Variable | Descripcion | Obligatoria |
|----------|-------------|-------------|
| `SECRET_KEY` | Clave secreta de Flask | Si |
| `JWT_SECRET_KEY` | Clave secreta de JWT | Si |
| `DATABASE_URL` | URL de conexion a PostgreSQL | Si |
| `POSTGRES_USER` | Usuario de PostgreSQL | Si (en Docker) |
| `POSTGRES_PASSWORD` | Password de PostgreSQL | Si |
| `POSTGRES_DB` | Nombre de la BD | Si |
| `DOMAIN` | Dominio para Traefik | Si (en Dokploy) |
| `JWT_COOKIE_SECURE` | Cookies seguras (HTTPS) | Si (produccion) |
| `STRIPE_SECRET_KEY` | Clave secreta de Stripe | Si (pagos) |
| `STRIPE_PUBLISHABLE_KEY` | Clave publica de Stripe | Si (pagos) |
| `STRIPE_WEBHOOK_SECRET` | Secret del webhook de Stripe | Si (pagos) |
| `SEED_DEMO_DATA` | Cargar datos demo al inicio | No |
| `ALLOW_INIT_DB_FALLBACK` | Fallback `init-db` si migraciones fallan | No (dev only) |

Ver `.env.example` para la lista completa.

## Comandos CLI utiles

```bash
# Aplicar migraciones
flask db upgrade

# Crear nueva migracion
flask db migrate -m "descripcion del cambio"

# Cargar datos demo
flask seed

# Inicializar BD sin migraciones (desarrollo)
flask init-db

# Shell de Flask
flask shell
```

## Tests

```bash
# Ejecutar suite de pruebas
pytest

# Con cobertura
pytest --cov=app --cov-report=html
```

Tambien existen scripts de verificacion por fase:

```bash
python verify_phase1.py  # Modelos
python verify_phase2.py  # API
python verify_phase3.py  # Frontend
python verify_phase4.py  # Docker/Dokploy
python verify_phase5.py  # Multi-tenancy
python verify_phase6.py  # Suscripciones
```

## Credenciales de demo

Despues de ejecutar `flask seed`:

| Rol | Email | Password |
|-----|-------|----------|
| Super-admin | super@medcenter.app | `Super123!` |
| Admin clinica | admin@medcenter.com | `Admin123!` |
| Medico | dr.house@medcenter.com | `Medico123!` |
| Medico | dra.grey@medcenter.com | `Medico123!` |
| Recepcionista | recep@medcenter.com | `Recep123!` |
| Paciente | juan@paciente.com | `Secret123` |

Mas detalles en [`USUARIOS.md`](USUARIOS.md).

## Estructura del proyecto

```
medical_clinic/
├── app/                    # Aplicacion Flask
│   ├── api/                # Blueprints (auth, appointments, etc.)
│   ├── models/             # Modelos SQLAlchemy
│   ├── schemas/            # Schemas Marshmallow
│   ├── services/           # Logica de negocio
│   ├── static/             # CSS, JS, imagenes
│   ├── templates/          # Plantillas Jinja2
│   ├── utils/              # Utilidades (decoradores, tenant, paginacion)
│   ├── __init__.py         # Application factory
│   ├── config.py           # Configuracion por entorno
│   ├── exceptions.py       # Excepciones del dominio
│   └── extensions.py       # Extensiones Flask
├── migrations/             # Migraciones Alembic (versionadas)
├── tests/                  # Tests pytest
├── docs/                   # Documentacion adicional
├── Dockerfile              # Imagen Docker multi-stage
├── docker-compose.yml      # Compose para Dokploy/produccion
├── docker-compose.override.yml  # Override local (puerto 8090)
├── docker-entrypoint.sh    # Entrypoint del contenedor
├── gunicorn.conf.py        # Configuracion de Gunicorn
├── requirements.txt        # Dependencias Python
├── seed_data.py            # Datos demo
├── run.py                  # Punto de entrada local
├── wsgi.py                 # Punto de entrada WSGI
├── DEPLOY.md               # Guia de despliegue
├── USUARIOS.md             # Usuarios y data de prueba
├── MARKETING.md            # Material de marketing
├── verify_phase*.py        # Verificaciones por fase
└── README.md               # Este archivo
```

## Seguridad

- Contrasenas hasheadas con Werkzeug PBKDF2-SHA256.
- JWT almacenados en cookies HttpOnly (anti-XSS).
- Proteccion CSRF en produccion.
- Contenedor Docker ejecutandose como usuario non-root.
- PostgreSQL no expuesto al host.
- Traefik aplica HSTS y redireccion HTTPS.

## Licencia

Proyecto privado. Todos los derechos reservados.
