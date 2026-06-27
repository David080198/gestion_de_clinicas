"""Blueprint del panel de control (dashboard) por rol.

Endpoints:
    GET /api/dashboard - Metricas personalizadas segun el rol del usuario.
"""

from __future__ import annotations

from flask import Blueprint, jsonify

from app.services.dashboard_service import DashboardService
from app.utils.decorators import current_user, login_required

dashboard_bp: Blueprint = Blueprint("dashboard", __name__)


@dashboard_bp.route("", methods=["GET"])
@login_required
def get_dashboard():
    """Retorna las metricas del panel segun el rol del usuario autenticado."""
    user = current_user()
    metrics = DashboardService.get_metrics(user)
    return jsonify({"dashboard": metrics})
