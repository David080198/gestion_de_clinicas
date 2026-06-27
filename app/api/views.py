"""Blueprint de vistas HTML (Frontend).

Sirve las plantillas Jinja2 con Tailwind CSS para todas las paginas
del sistema: login, registro, dashboard, calendario, citas, expediente
y recetas. Las paginas protegidas validan la sesion JWT via /api/auth/me
en el lado cliente (JavaScript) y redirigen al login si no hay sesion.
"""

from __future__ import annotations

from flask import Blueprint, render_template, jsonify

views_bp: Blueprint = Blueprint("views", __name__)


# ============================================================
# Health checks (para Dokploy / Traefik)
# ============================================================

@views_bp.route("/")
def index():
    """Página de bienvenida / landing page."""
    return render_template("welcome.html")


@views_bp.route("/health")
def health():
    """Health check ligero para el balanceador."""
    return jsonify({"status": "healthy"}), 200


# ============================================================
# Autenticacion (paginas publicas)
# ============================================================

@views_bp.route("/login")
def login_page():
    """Pagina de inicio de sesion."""
    return render_template("auth/login.html")


@views_bp.route("/register")
def register_page():
    """Pagina de registro de paciente."""
    return render_template("auth/register.html")


# ============================================================
# Paginas protegidas (validan JWT en el cliente)
# ============================================================

@views_bp.route("/dashboard")
def dashboard_page():
    """Dashboard personalizado por rol."""
    return render_template("dashboard/index.html")


@views_bp.route("/appointments/calendar")
def calendar_page():
    """Calendario interactivo de citas."""
    return render_template("appointments/calendar.html")


@views_bp.route("/appointments")
def appointments_list_page():
    """Lista de citas del usuario."""
    return render_template("appointments/list.html")


@views_bp.route("/appointments/new")
def new_appointment_page():
    """Formulario para agendar nueva cita."""
    return render_template("appointments/new.html")


@views_bp.route("/appointments/<int:appointment_id>")
def appointment_detail_page(appointment_id: int):
    """Detalle de una cita (reutiliza el calendario con modal abierto)."""
    return render_template("appointments/calendar.html")


@views_bp.route("/appointments/<int:appointment_id>/edit")
def edit_appointment_page(appointment_id: int):
    """Pagina de reprogramacion de cita."""
    return render_template("appointments/new.html")


# ============================================================
# Modulo medico
# ============================================================

@views_bp.route("/medical/consult/<int:appointment_id>")
def consult_page(appointment_id: int):
    """Formulario de consulta medica (expediente + receta)."""
    return render_template("medical/consult.html")


@views_bp.route("/medical/history")
def medical_history_page():
    """Historial medico del paciente."""
    return render_template("medical/history.html")


@views_bp.route("/prescriptions")
def prescriptions_page():
    """Listado de recetas del paciente."""
    return render_template("medical/prescriptions.html")


# ============================================================
# Placeholders para modulos futuros (sidebar)
# ============================================================

@views_bp.route("/waiting-room")
def waiting_room_page():
    """Sala de espera (recepcionista)."""
    return render_template("dashboard/index.html")


@views_bp.route("/patients")
def patients_page():
    """Busqueda de pacientes."""
    return render_template("dashboard/index.html")


@views_bp.route("/medical/records")
def medical_records_page():
    """Listado de expedientes (medico)."""
    return render_template("medical/history.html")


@views_bp.route("/staff")
def staff_page():
    """Gestion de personal (admin)."""
    return render_template("dashboard/index.html")


@views_bp.route("/reports")
def reports_page():
    """Reportes financieros (admin)."""
    return render_template("dashboard/index.html")
