"""Inicializacion centralizada de extensiones Flask.

Mantener las instancias de extensiones separadas del factory de la aplicacion
evita importes circulares entre modelos, blueprints y la app principal.
"""

from __future__ import annotations

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager

# Instancia unica de SQLAlchemy (ORM)
db: SQLAlchemy = SQLAlchemy()

# Migraciones Alembic
migrate: Migrate = Migrate()

# Gestion de tokens JWT
jwt: JWTManager = JWTManager()
