"""Configuracion centralizada de la aplicacion Flask.

Define distintas configuraciones segun el entorno (development, testing,
production) y lee las variables sensibles desde el entorno para que Dokploy
pueda inyectarlas de forma segura en el despliegue.
"""

from __future__ import annotations

import os
from datetime import timedelta
from typing import Any

from dotenv import load_dotenv
from sqlalchemy.pool import StaticPool

load_dotenv()


def _get_bool(name: str, default: bool = False) -> bool:
    """Lee una variable de entorno como booleano de forma segura."""
    value: str | None = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    """Lee una variable de entorno como entero con valor por defecto."""
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


class BaseConfig:
    """Configuracion base compartida por todos los entornos."""

    # --- Aplicacion ---
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    PROPAGATE_EXCEPTIONS: bool = True
    JSON_SORT_KEYS: bool = False
    JSONIFY_PRETTYPRINT_REGULAR: bool = False

    # --- Base de datos ---
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "DATABASE_URL",
        "postgresql://clinic_user:clinic_password@db:5432/clinic_db",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_ENGINE_OPTIONS: dict[str, Any] = {
        "pool_size": 10,
        "pool_recycle": 3600,
        "pool_pre_ping": True,
        "max_overflow": 20,
    }

    # --- JWT ---
    JWT_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", "jwt-dev-secret")
    JWT_ACCESS_TOKEN_EXPIRES: timedelta = timedelta(
        seconds=_get_int("JWT_ACCESS_TOKEN_EXPIRES", 3600)
    )
    JWT_REFRESH_TOKEN_EXPIRES: timedelta = timedelta(days=30)
    JWT_TOKEN_LOCATION: list[str] = ["cookies"]
    JWT_COOKIE_SECURE: bool = _get_bool("JWT_COOKIE_SECURE", False)
    JWT_COOKIE_HTTPONLY: bool = True
    JWT_COOKIE_SAMESITE: str = os.environ.get("JWT_COOKIE_SAMESITE", "Lax")
    JWT_COOKIE_CSRF_PROTECT: bool = _get_bool("JWT_COOKIE_CSRF_PROTECT", True)
    JWT_ERROR_MESSAGE_KEY: str = "error"

    # --- Clinica ---
    CLINIC_NAME: str = os.environ.get("CLINIC_NAME", "MedCenter Premium")
    CLINIC_TIMEZONE: str = os.environ.get("CLINIC_TIMEZONE", "America/Mexico_City")
    CLINIC_CURRENCY: str = os.environ.get("CLINIC_CURRENCY", "MXN")

    # --- Pagination ---
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100


class DevelopmentConfig(BaseConfig):
    """Configuracion para desarrollo local."""

    DEBUG: bool = True
    SQLALCHEMY_ECHO: bool = False
    JWT_COOKIE_SECURE: bool = False
    JWT_COOKIE_CSRF_PROTECT: bool = False
    PROPAGATE_EXCEPTIONS: bool = True


class TestingConfig(BaseConfig):
    """Configuracion para pruebas unitarias/integracion."""

    TESTING: bool = True
    DEBUG: bool = True
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "TEST_DATABASE_URL", "sqlite:///:memory:"
    )
    # SQLite en memoria requiere StaticPool para compartir la misma conexion
    # entre el contexto manual y el test client de Flask dentro del mismo test.
    SQLALCHEMY_ENGINE_OPTIONS: dict[str, Any] = {
        "poolclass": StaticPool,
        "connect_args": {"check_same_thread": False},
    }
    JWT_COOKIE_SECURE: bool = False
    JWT_COOKIE_CSRF_PROTECT: bool = False
    JWT_ACCESS_TOKEN_EXPIRES: timedelta = timedelta(seconds=3600)
    # Aceptar tokens tanto en cookies como en headers para facilitar testing
    JWT_TOKEN_LOCATION: list[str] = ["cookies", "headers"]


class ProductionConfig(BaseConfig):
    """Configuracion para produccion (Dokploy / Docker).

    Los valores de seguridad (JWT_COOKIE_SECURE, CSRF) se leen del entorno
    para permitir ajustarlos en pruebas locales sin HTTPS; por defecto son
    True para produccion detras de Traefik.
    """

    DEBUG: bool = False
    TESTING: bool = False
    JWT_COOKIE_SECURE: bool = _get_bool("JWT_COOKIE_SECURE", True)
    JWT_COOKIE_CSRF_PROTECT: bool = _get_bool("JWT_COOKIE_CSRF_PROTECT", True)
    PREFERRED_URL_SCHEME: str = "https"


# Mapeo de entornos
config_map: dict[str, type[BaseConfig]] = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(env_name: str | None = None) -> type[BaseConfig]:
    """Retorna la clase de configuracion correspondiente al entorno.

    Args:
        env_name: Nombre del entorno. Si es None, se lee de FLASK_ENV.

    Returns:
        Clase de configuracion a usar.

    Raises:
        ValueError: Si el entorno solicitado no esta definido.
    """
    env: str = (env_name or os.environ.get("FLASK_ENV", "production")).lower()
    config: type[BaseConfig] | None = config_map.get(env)
    if config is None:
        raise ValueError(
            f"Entorno '{env}' no reconocido. "
            f"Opciones validas: {list(config_map.keys())}"
        )
    return config
