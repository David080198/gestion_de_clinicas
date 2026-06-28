"""Application factory del sistema de gestion de consultorios medicos.

Construye la aplicacion Flask de forma modular para permitir multiples
entornos (dev, test, prod) y facilitar las pruebas unitarias.
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Flask, jsonify, render_template
from flask.json.provider import DefaultJSONProvider
from flask_jwt_extended import JWTManager

from .config import BaseConfig, get_config
from .extensions import db, migrate, jwt
from .exceptions import ClinicBaseError


def create_app(config_name: str | None = None) -> Flask:
    """Crea y configura una instancia de la aplicacion Flask.

    Args:
        config_name: Nombre del entorno (development, testing, production).
            Si es None, se lee de la variable FLASK_ENV.

    Returns:
        Instancia configurada y lista de la aplicacion Flask.
    """
    config_class: type[BaseConfig] = get_config(config_name)

    app: Flask = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config_class)

    # --- Logging basico ---
    logging.basicConfig(
        level=logging.INFO if not app.config.get("DEBUG") else logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # --- Inicializacion de extensiones ---
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    # --- Callbacks JWT ---
    _register_jwt_callbacks(jwt)

    # --- Manejadores de errores ---
    _register_error_handlers(app)

    # --- Registro de Blueprints (Fase 2) ---
    _register_blueprints(app)

    # --- Comandos CLI ---
    _register_cli_commands(app)

    app.logger.info("Aplicacion iniciada en entorno: %s", config_class.__name__)
    return app


def _register_jwt_callbacks(jwt_manager: JWTManager) -> None:
    """Configura los callbacks de respuesta de errores de JWT."""

    @jwt_manager.expired_token_loader
    def expired_token_callback(jwt_header: dict, jwt_payload: dict) -> Any:
        return jsonify({"error": "Tu sesion ha expirado.", "code": 401}), 401

    @jwt_manager.invalid_token_loader
    def invalid_token_callback(error: str) -> Any:
        return jsonify({"error": "Token invalido.", "code": 422}), 422

    @jwt_manager.unauthorized_loader
    def missing_token_callback(error: str) -> Any:
        return jsonify({"error": "Token de acceso requerido.", "code": 401}), 401

    @jwt_manager.revoked_token_loader
    def revoked_token_callback(jwt_header: dict, jwt_payload: dict) -> Any:
        return jsonify({"error": "Token revocado.", "code": 401}), 401


def _register_error_handlers(app: Flask) -> None:
    """Registra manejadores centralizados de excepciones del dominio.

    Las rutas /api/* responden JSON; las rutas HTML responden plantillas.
    """

    @app.errorhandler(ClinicBaseError)
    def handle_clinic_error(err: ClinicBaseError) -> Any:
        return jsonify(err.to_dict()), err.status_code

    @app.errorhandler(404)
    def handle_not_found(err: Any) -> Any:
        from flask import request
        if request.path.startswith("/api/"):
            return jsonify({"error": "Recurso no encontrado.", "code": 404}), 404
        return render_template(
            "errors/error.html",
            code=404,
            title="Pagina no encontrada",
            message="La pagina que buscas no existe o fue movida.",
        ), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(err: Any) -> Any:
        return jsonify({"error": "Metodo no permitido.", "code": 405}), 405

    @app.errorhandler(403)
    def handle_forbidden(err: Any) -> Any:
        from flask import request
        if request.path.startswith("/api/"):
            return jsonify({"error": "Acceso denegado.", "code": 403}), 403
        return render_template(
            "errors/error.html",
            code=403,
            title="Acceso denegado",
            message="No tienes permiso para acceder a esta pagina.",
        ), 403

    @app.errorhandler(500)
    def handle_internal_error(err: Any) -> Any:
        app.logger.exception("Error interno del servidor: %s", err)
        from flask import request
        if request.path.startswith("/api/"):
            return jsonify({"error": "Error interno del servidor.", "code": 500}), 500
        return render_template(
            "errors/error.html",
            code=500,
            title="Error del servidor",
            message="Ocurrio un error inesperado. Intentalo de nuevo mas tarde.",
        ), 500


def _register_blueprints(app: Flask) -> None:
    """Registra los blueprints de la API y las vistas.

    Los endpoints se organizan en blueprints por dominio para mantener
    rutas agrupadas y prefijos consistentes.
    """
    # Importa los modelos para que SQLAlchemy los registre en el metadata
    from . import models  # noqa: F401

    from .api.auth import auth_bp
    from .api.appointments import appointments_bp
    from .api.medical_records import medical_records_bp
    from .api.dashboard import dashboard_bp
    from .api.clinics import clinics_bp
    from .api.subscriptions import subscriptions_bp
    from .api.stripe import stripe_bp
    from .api.views import views_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(appointments_bp, url_prefix="/api/appointments")
    app.register_blueprint(medical_records_bp, url_prefix="/api/medical")
    app.register_blueprint(dashboard_bp, url_prefix="/api/dashboard")
    app.register_blueprint(clinics_bp, url_prefix="/api/clinics")
    app.register_blueprint(subscriptions_bp, url_prefix="/api/subscriptions")
    app.register_blueprint(stripe_bp)
    app.register_blueprint(views_bp)

    app.logger.info(
        "Blueprints registrados: auth, appointments, medical, dashboard, clinics, subscriptions, stripe, views."
    )


def _register_cli_commands(app: Flask) -> None:
    """Registra comandos CLI personalizados para inicializacion de datos."""

    @app.cli.command("init-db")
    def init_db() -> None:
        """Crea todas las tablas (uso en desarrollo sin migraciones)."""
        db.create_all()
        print("Base de datos inicializada.")

    @app.cli.command("seed")
    def seed_db() -> None:
        """Puebla la base con datos demo (super-admin + clinica demo)."""
        from seed_data import run as run_seed
        run_seed()
        print("Seed de datos demo completado.")
