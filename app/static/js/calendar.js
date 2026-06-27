/* ============================================================
   Calendario de citas - Vista mensual interactiva
   ============================================================ */

const CalendarView = {
    current: new Date(),
    appointments: [],
    user: null,

    async init() {
        this.user = await AppAuth.requireAuth();
        if (!this.user) return;

        // Mostrar boton "Nueva cita" para roles que pueden agendar
        const canCreate = ['recepcionista', 'admin', 'paciente'].includes(this.user.role);
        const btn = document.getElementById('new-appointment-btn');
        if (canCreate && btn) btn.classList.remove('hidden');

        await this.loadAppointments();
        this.render();
    },

    // ============================================================
    // Carga de datos
    // ============================================================
    async loadAppointments() {
        const year = this.current.getFullYear();
        const month = this.current.getMonth();
        const start = new Date(year, month, 1).toISOString().split('T')[0];
        const end = new Date(year, month + 1, 0).toISOString().split('T')[0];

        try {
            const data = await Api.get(`${Endpoints.appointments.calendar}?start=${start}&end=${end}`);
            this.appointments = data.items || [];
        } catch (err) {
            Toasts.error('Error al cargar las citas: ' + err.message);
            this.appointments = [];
        }
    },

    // ============================================================
    // Renderizado
    // ============================================================
    render() {
        // Etiqueta del mes
        const label = document.getElementById('calendar-month-label');
        const months = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
        label.textContent = `${months[this.current.getMonth()]} ${this.current.getFullYear()}`;

        const grid = document.getElementById('calendar-grid');
        const year = this.current.getFullYear();
        const month = this.current.getMonth();

        // Primer dia del mes y su weekday (0=Domingo -> ajustar a Lunes=0)
        const firstDay = new Date(year, month, 1);
        let firstWeekday = firstDay.getDay() - 1; // Domingo=6, Lunes=0
        if (firstWeekday < 0) firstWeekday = 6; // Domingo -> 6

        const daysInMonth = new Date(year, month + 1, 0).getDate();
        const today = new Date();
        const todayStr = today.toDateString();

        let html = '';

        // Celdas vacias antes del primer dia
        for (let i = 0; i < firstWeekday; i++) {
            html += '<div class="calendar-day calendar-day-disabled rounded-lg"></div>';
        }

        // Dias del mes
        for (let day = 1; day <= daysInMonth; day++) {
            const date = new Date(year, month, day);
            const dateStr = date.toISOString().split('T')[0];
            const isToday = date.toDateString() === todayStr;
            const dayAppointments = this.appointments.filter(a =>
                a.start_time.startsWith(dateStr)
            );

            const dayClass = isToday ? 'calendar-day calendar-day-today rounded-lg' : 'calendar-day rounded-lg';
            let eventsHtml = '';

            // Mostrar maximo 3 eventos por dia
            const maxShow = 3;
            dayAppointments.slice(0, maxShow).forEach(a => {
                const color = this.eventColor(a.status);
                const time = Utils.formatTime(a.start_time);
                const label = this.user.role === 'medico' ? (a.patient_name || '') : (a.doctor_name || '');
                eventsHtml += `<div class="calendar-event ${color}" onclick="CalendarView.showDetail(${a.id})" title="${time} - ${label}">${time} ${label}</div>`;
            });
            if (dayAppointments.length > maxShow) {
                eventsHtml += `<div class="text-xs text-slate-400 mt-1 cursor-pointer" onclick="CalendarView.showDayList('${dateStr}')">+${dayAppointments.length - maxShow} mas</div>`;
            }

            html += `
                <div class="${dayClass}" onclick="CalendarView.onDayClick('${dateStr}')">
                    <p class="text-sm font-semibold ${isToday ? 'text-primary-700' : 'text-slate-700'}">${day}</p>
                    ${eventsHtml}
                </div>`;
        }

        grid.innerHTML = html;
    },

    eventColor(status) {
        const colors = {
            pendiente: 'bg-amber-100 text-amber-800',
            confirmada: 'bg-blue-100 text-blue-800',
            en_consulta: 'bg-primary-100 text-primary-800',
            completada: 'bg-emerald-100 text-emerald-800',
            cancelada: 'bg-red-100 text-red-800 line-through',
        };
        return colors[status] || colors.pendiente;
    },

    // ============================================================
    // Navegacion
    // ============================================================
    prevMonth() {
        this.current.setMonth(this.current.getMonth() - 1);
        this.init();
    },

    nextMonth() {
        this.current.setMonth(this.current.getMonth() + 1);
        this.init();
    },

    today() {
        this.current = new Date();
        this.init();
    },

    // ============================================================
    // Interacciones
    // ============================================================
    onDayClick(dateStr) {
        // Recepcionista/admin/paciente: ir a crear cita con fecha preseleccionada
        if (['recepcionista', 'admin', 'paciente'].includes(this.user.role)) {
            window.location.href = `/appointments/new?date=${dateStr}`;
        }
    },

    async showDetail(appointmentId) {
        try {
            // Buscar en cache primero
            let apt = this.appointments.find(a => a.id === appointmentId);
            if (!apt) {
                const data = await Api.get(`${Endpoints.appointments.list}/${appointmentId}`);
                apt = data.appointment;
            }
            this.openModal(this.renderDetail(apt));
        } catch (err) {
            Toasts.error('Error al cargar la cita: ' + err.message);
        }
    },

    showDayList(dateStr) {
        const dayAppts = this.appointments.filter(a => a.start_time.startsWith(dateStr));
        const dateLabel = new Date(dateStr).toLocaleDateString('es-ES', {
            weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
        });
        const listHtml = dayAppts.map(a => `
            <div class="flex items-center gap-4 py-3 border-b border-slate-100 last:border-0 cursor-pointer hover:bg-slate-50 rounded-xl px-3"
                 onclick="CalendarView.showDetail(${a.id})">
                <p class="text-sm font-bold text-primary-600 min-w-[60px]">${Utils.formatTime(a.start_time)}</p>
                <div class="flex-1">
                    <p class="text-sm font-semibold text-slate-800">${this.user.role === 'medico' ? a.patient_name : a.doctor_name}</p>
                </div>
                ${Utils.statusBadge(a.status)}
            </div>
        `).join('');
        this.openModal(`<h3 class="text-lg font-bold text-slate-800 mb-4 capitalize">${dateLabel}</h3><div>${listHtml}</div>`);
    },

    renderDetail(a) {
        const canEdit = ['recepcionista', 'admin'].includes(this.user.role);
        const canCancel = ['recepcionista', 'admin', 'paciente'].includes(this.user.role);
        const canAttend = this.user.role === 'medico';

        return `
            <div class="flex items-start justify-between mb-4">
                <div>
                    <h3 class="text-xl font-bold text-slate-800">Detalle de cita</h3>
                    <p class="text-sm text-slate-500 mt-1">#${a.id}</p>
                </div>
                <button onclick="CalendarView.closeModal()" class="text-slate-400 hover:text-slate-600 p-2">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
                </button>
            </div>

            <div class="space-y-3 mb-6">
                <div class="flex items-center justify-between py-2 border-b border-slate-100">
                    <span class="text-sm text-slate-500">Fecha</span>
                    <span class="text-sm font-semibold text-slate-800">${Utils.formatDate(a.start_time)}</span>
                </div>
                <div class="flex items-center justify-between py-2 border-b border-slate-100">
                    <span class="text-sm text-slate-500">Hora</span>
                    <span class="text-sm font-semibold text-slate-800">${Utils.formatTime(a.start_time)} - ${Utils.formatTime(a.end_time)}</span>
                </div>
                <div class="flex items-center justify-between py-2 border-b border-slate-100">
                    <span class="text-sm text-slate-500">Paciente</span>
                    <span class="text-sm font-semibold text-slate-800">${a.patient_name || '-'}</span>
                </div>
                <div class="flex items-center justify-between py-2 border-b border-slate-100">
                    <span class="text-sm text-slate-500">Medico</span>
                    <span class="text-sm font-semibold text-slate-800">${a.doctor_name || '-'}</span>
                </div>
                <div class="flex items-center justify-between py-2 border-b border-slate-100">
                    <span class="text-sm text-slate-500">Especialidad</span>
                    <span class="text-sm font-semibold text-slate-800">${a.doctor_specialty || '-'}</span>
                </div>
                <div class="flex items-center justify-between py-2 border-b border-slate-100">
                    <span class="text-sm text-slate-500">Estado</span>
                    ${Utils.statusBadge(a.status)}
                </div>
                ${a.reason ? `<div class="py-2 border-b border-slate-100"><p class="text-sm text-slate-500 mb-1">Motivo</p><p class="text-sm text-slate-800">${a.reason}</p></div>` : ''}
            </div>

            <div class="flex gap-3">
                ${canEdit && a.status !== 'cancelada' && a.status !== 'completada' ? `
                    <a href="/appointments/${a.id}/edit" class="btn-secondary flex-1 justify-center text-sm">Reprogramar</a>
                ` : ''}
                ${canAttend && a.status === 'confirmada' ? `
                    <a href="/medical/consult/${a.id}" class="btn-primary flex-1 justify-center text-sm">Iniciar consulta</a>
                ` : ''}
                ${canAttend && a.status === 'en_consulta' ? `
                    <a href="/medical/consult/${a.id}" class="btn-primary flex-1 justify-center text-sm">Continuar consulta</a>
                ` : ''}
                ${canCancel && a.status !== 'cancelada' && a.status !== 'completada' ? `
                    <button onclick="CalendarView.cancelAppointment(${a.id})" class="btn-secondary text-sm text-red-600 border-red-200 hover:bg-red-50">Cancelar cita</button>
                ` : ''}
            </div>
        `;
    },

    async cancelAppointment(id) {
        if (!confirm('¿Estas seguro de cancelar esta cita?')) return;
        try {
            await Api.patch(`${Endpoints.appointments.list}/${id}/status`, { status: 'cancelada' });
            Toasts.success('Cita cancelada');
            this.closeModal();
            await this.loadAppointments();
            this.render();
        } catch (err) {
            Toasts.error(err.message);
        }
    },

    // ============================================================
    // Modal
    // ============================================================
    openModal(html) {
        const modal = document.getElementById('appointment-modal');
        const body = document.getElementById('modal-body');
        body.innerHTML = html;
        modal.classList.remove('hidden');
    },

    closeModal(event) {
        if (event && event.target !== event.currentTarget) return;
        document.getElementById('appointment-modal').classList.add('hidden');
    },
};

document.addEventListener('DOMContentLoaded', () => CalendarView.init());
