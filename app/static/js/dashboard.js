/* ============================================================
   Dashboard - Renderiza metricas personalizadas por rol
   ============================================================ */

const DashboardView = {
    async init() {
        const user = await AppAuth.requireAuth();
        if (!user) return;

        try {
            const data = await Api.get(Endpoints.dashboard);
            const dash = data.dashboard;

            // Actualizar titulo de la pagina
            const titleEl = document.getElementById('page-title');
            const greetings = this.greeting();
            titleEl.textContent = `${greetings}, ${user.first_name}`;

            // Renderizar segun rol
            let html = '';
            switch (dash.role) {
                case 'admin':        html = this.renderAdmin(dash); break;
                case 'medico':       html = this.renderMedico(dash); break;
                case 'recepcionista':html = this.renderRecepcionista(dash); break;
                case 'paciente':     html = this.renderPaciente(dash); break;
            }

            document.getElementById('loading-skeleton').classList.add('hidden');
            const real = document.getElementById('dashboard-real');
            real.classList.remove('hidden');
            real.innerHTML = html;
            real.classList.add('animate-fade-in');

            // Renderizar grafica si es admin
            if (dash.role === 'admin' && dash.monthly_revenue) {
                this.renderRevenueChart(dash.monthly_revenue);
            }
        } catch (err) {
            Toasts.error('Error al cargar el dashboard: ' + err.message);
        }
    },

    greeting() {
        const h = new Date().getHours();
        if (h < 12) return 'Buenos dias';
        if (h < 19) return 'Buenas tardes';
        return 'Buenas noches';
    },

    // ============================================================
    // Admin
    // ============================================================
    renderAdmin(d) {
        const totals = d.totals || {};
        const byStatus = d.appointments_by_status || {};
        const topDocs = d.top_doctors || [];

        const statusCards = Object.entries(byStatus).map(([status, count]) =>
            `<div class="flex items-center justify-between py-2">
                <span class="text-sm text-slate-600 capitalize">${status.replace('_', ' ')}</span>
                <span class="font-bold text-slate-800">${count}</span>
            </div>`
        ).join('');

        const topDocsHtml = topDocs.length > 0 ? topDocs.map((doc, i) => `
            <div class="flex items-center gap-4 py-3 ${i < topDocs.length - 1 ? 'border-b border-slate-100' : ''}">
                <div class="w-8 h-8 rounded-lg bg-primary-100 text-primary-700 flex items-center justify-center text-sm font-bold">${i + 1}</div>
                <div class="flex-1">
                    <p class="text-sm font-semibold text-slate-800">${doc.name}</p>
                    <p class="text-xs text-slate-500">${doc.specialty}</p>
                </div>
                <div class="text-right">
                    <p class="text-lg font-bold text-primary-600">${doc.appointments}</p>
                    <p class="text-xs text-slate-400">citas</p>
                </div>
            </div>
        `).join('') : '<p class="text-slate-400 text-sm py-4 text-center">Sin datos este mes</p>';

        return `
            <!-- Tarjetas de metricas -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <div class="card-premium p-6">
                    <div class="flex items-center gap-4">
                        <div class="w-12 h-12 rounded-xl bg-primary-100 flex items-center justify-center">
                            <svg class="w-6 h-6 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0V11.25A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"/></svg>
                        </div>
                        <div>
                            <p class="text-sm text-slate-500">Citas del mes</p>
                            <p class="text-2xl font-bold text-slate-800">${totals.appointments_this_month || 0}</p>
                        </div>
                    </div>
                </div>
                <div class="card-premium p-6">
                    <div class="flex items-center gap-4">
                        <div class="w-12 h-12 rounded-xl bg-emerald-100 flex items-center justify-center">
                            <svg class="w-6 h-6 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                        </div>
                        <div>
                            <p class="text-sm text-slate-500">Ingresos del mes</p>
                            <p class="text-2xl font-bold text-emerald-600">$${this.formatMoney(totals.revenue_this_month || 0)}</p>
                        </div>
                    </div>
                </div>
                <div class="card-premium p-6">
                    <div class="flex items-center gap-4">
                        <div class="w-12 h-12 rounded-xl bg-amber-100 flex items-center justify-center">
                            <svg class="w-6 h-6 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M17.982 18.725A7.488 7.488 0 0012 15.75a7.488 7.488 0 00-5.982 2.975m11.963 0a9 9 0 10-11.963 0m11.963 0A8.966 8.966 0 0112 21a8.966 8.966 0 01-5.982-2.275M15 9.75a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
                        </div>
                        <div>
                            <p class="text-sm text-slate-500">Medicos activos</p>
                            <p class="text-2xl font-bold text-slate-800">${topDocs.length}</p>
                        </div>
                    </div>
                </div>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
                <!-- Citas por estado -->
                <div class="card-premium p-6">
                    <h3 class="text-lg font-bold text-slate-800 mb-4">Citas por estado</h3>
                    <div class="divide-y divide-slate-100">${statusCards || '<p class="text-slate-400 text-sm">Sin datos</p>'}</div>
                </div>

                <!-- Medicos mas solicitados -->
                <div class="card-premium p-6">
                    <h3 class="text-lg font-bold text-slate-800 mb-4">Medicos mas solicitados</h3>
                    ${topDocsHtml}
                </div>
            </div>

            <!-- Grafica de ingresos -->
            <div class="card-premium p-6">
                <h3 class="text-lg font-bold text-slate-800 mb-4">Ingresos mensuales (ultimos 6 meses)</h3>
                <canvas id="revenue-chart" height="80"></canvas>
            </div>
        `;
    },

    // ============================================================
    // Medico
    // ============================================================
    renderMedico(d) {
        const appts = d.today_appointments || [];
        const counts = d.counts || {};

        const apptsHtml = appts.length > 0 ? appts.map(a => `
            <div class="flex items-center gap-4 py-3 border-b border-slate-100 last:border-0 hover:bg-slate-50 rounded-xl px-3 transition-colors cursor-pointer"
                 onclick="window.location.href='/appointments/${a.id}'">
                <div class="text-center min-w-[60px]">
                    <p class="text-sm font-bold text-primary-600">${Utils.formatTime(a.start_time)}</p>
                    <p class="text-xs text-slate-400">${Utils.formatTime(a.end_time)}</p>
                </div>
                <div class="w-px h-10 bg-slate-200"></div>
                <div class="flex-1">
                    <p class="text-sm font-semibold text-slate-800">${a.patient_name || 'Paciente'}</p>
                    <p class="text-xs text-slate-500">${a.reason || 'Sin motivo especificado'}</p>
                </div>
                ${Utils.statusBadge(a.status)}
            </div>
        `).join('') : '<p class="text-slate-400 text-sm py-8 text-center">No tienes citas hoy</p>';

        return `
            <!-- Contadores rapidos -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <div class="card-premium p-6">
                    <p class="text-sm text-slate-500 mb-1">Citas de hoy</p>
                    <p class="text-3xl font-bold text-slate-800">${counts.today || 0}</p>
                </div>
                <div class="card-premium p-6">
                    <p class="text-sm text-slate-500 mb-1">En consulta</p>
                    <p class="text-3xl font-bold text-primary-600">${counts.in_consultation || 0}</p>
                </div>
                <div class="card-premium p-6">
                    <p class="text-sm text-slate-500 mb-1">Completadas hoy</p>
                    <p class="text-3xl font-bold text-emerald-600">${counts.completed_today || 0}</p>
                </div>
            </div>

            <!-- Citas del dia -->
            <div class="card-premium p-6">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-lg font-bold text-slate-800">Citas de hoy</h3>
                    <a href="/appointments/calendar" class="text-sm text-primary-600 hover:text-primary-700 font-semibold">Ver calendario</a>
                </div>
                ${apptsHtml}
            </div>
        `;
    },

    // ============================================================
    // Recepcionista
    // ============================================================
    renderRecepcionista(d) {
        const waiting = d.waiting_room || [];

        const waitingHtml = waiting.length > 0 ? waiting.map(w => `
            <div class="flex items-center gap-4 py-3 border-b border-slate-100 last:border-0 hover:bg-slate-50 rounded-xl px-3 transition-colors">
                <div class="w-10 h-10 rounded-full bg-primary-100 text-primary-700 flex items-center justify-center font-semibold text-sm">
                    ${(w.patient_name || '?')[0]}
                </div>
                <div class="flex-1">
                    <p class="text-sm font-semibold text-slate-800">${w.patient_name}</p>
                    <p class="text-xs text-slate-500">DOC: ${w.document_number} - ${w.doctor_name}</p>
                </div>
                <div class="text-right">
                    <p class="text-sm font-bold text-slate-700">${Utils.formatTime(w.start_time)}</p>
                    ${Utils.statusBadge(w.status)}
                </div>
            </div>
        `).join('') : '<p class="text-slate-400 text-sm py-8 text-center">No hay pacientes en espera</p>';

        return `
            <!-- Contador -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
                <div class="card-premium p-6">
                    <div class="flex items-center gap-4">
                        <div class="w-12 h-12 rounded-xl bg-primary-100 flex items-center justify-center">
                            <svg class="w-6 h-6 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0V11.25A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"/></svg>
                        </div>
                        <div>
                            <p class="text-sm text-slate-500">Citas totales de hoy</p>
                            <p class="text-2xl font-bold text-slate-800">${d.total_appointments_today || 0}</p>
                        </div>
                    </div>
                </div>
                <div class="card-premium p-6">
                    <div class="flex items-center gap-4">
                        <div class="w-12 h-12 rounded-xl bg-amber-100 flex items-center justify-center">
                            <svg class="w-6 h-6 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                        </div>
                        <div>
                            <p class="text-sm text-slate-500">En sala de espera</p>
                            <p class="text-2xl font-bold text-amber-600">${waiting.length}</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Accesos rapidos -->
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
                <a href="/appointments/new" class="card-premium p-6 text-center hover:shadow-md transition-shadow group">
                    <svg class="w-8 h-8 text-primary-600 mx-auto mb-2 group-hover:scale-110 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15"/></svg>
                    <p class="text-sm font-semibold text-slate-700">Nueva cita</p>
                </a>
                <a href="/patients" class="card-premium p-6 text-center hover:shadow-md transition-shadow group">
                    <svg class="w-8 h-8 text-primary-600 mx-auto mb-2 group-hover:scale-110 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"/></svg>
                    <p class="text-sm font-semibold text-slate-700">Buscar paciente</p>
                </a>
                <a href="/appointments/calendar" class="card-premium p-6 text-center hover:shadow-md transition-shadow group">
                    <svg class="w-8 h-8 text-primary-600 mx-auto mb-2 group-hover:scale-110 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75"/></svg>
                    <p class="text-sm font-semibold text-slate-700">Calendario</p>
                </a>
            </div>

            <!-- Sala de espera -->
            <div class="card-premium p-6">
                <h3 class="text-lg font-bold text-slate-800 mb-4">Pacientes en sala de espera</h3>
                ${waitingHtml}
            </div>
        `;
    },

    // ============================================================
    // Paciente
    // ============================================================
    renderPaciente(d) {
        const upcoming = d.upcoming || [];
        const counts = d.counts || {};

        const upcomingHtml = upcoming.length > 0 ? upcoming.map(a => `
            <div class="flex items-center gap-4 py-3 border-b border-slate-100 last:border-0 hover:bg-slate-50 rounded-xl px-3 transition-colors">
                <div class="text-center min-w-[70px]">
                    <p class="text-xs text-slate-400">${new Date(a.start_time).toLocaleDateString('es-ES', {month:'short', day:'numeric'})}</p>
                    <p class="text-sm font-bold text-primary-600">${Utils.formatTime(a.start_time)}</p>
                </div>
                <div class="w-px h-10 bg-slate-200"></div>
                <div class="flex-1">
                    <p class="text-sm font-semibold text-slate-800">${a.doctor_name}</p>
                    <p class="text-xs text-slate-500">${a.doctor_specialty}</p>
                </div>
                ${Utils.statusBadge(a.status)}
            </div>
        `).join('') : '<p class="text-slate-400 text-sm py-8 text-center">No tienes citas proximas. <a href="/appointments/new" class="text-primary-600 font-semibold">Agenda una aqui</a></p>';

        return `
            <!-- Resumen -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <div class="card-premium p-6 text-center">
                    <p class="text-sm text-slate-500 mb-1">Citas proximas</p>
                    <p class="text-3xl font-bold text-primary-600">${upcoming.length}</p>
                </div>
                <div class="card-premium p-6 text-center">
                    <p class="text-sm text-slate-500 mb-1">Consultas historicas</p>
                    <p class="text-3xl font-bold text-slate-800">${counts.history_records || 0}</p>
                </div>
                <div class="card-premium p-6 text-center">
                    <p class="text-sm text-slate-500 mb-1">Recetas emitidas</p>
                    <p class="text-3xl font-bold text-emerald-600">${counts.prescriptions || 0}</p>
                </div>
            </div>

            <!-- Proximas citas -->
            <div class="card-premium p-6 mb-6">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-lg font-bold text-slate-800">Mis proximas citas</h3>
                    <a href="/appointments/new" class="btn-secondary text-sm">Agendar nueva</a>
                </div>
                ${upcomingHtml}
            </div>

            <!-- Accesos rapidos -->
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <a href="/prescriptions" class="card-premium p-6 hover:shadow-md transition-shadow group">
                    <svg class="w-8 h-8 text-primary-600 mb-2 group-hover:scale-110 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
                    <p class="text-sm font-semibold text-slate-700">Mis recetas</p>
                    <p class="text-xs text-slate-400">Descarga tus recetas en PDF</p>
                </a>
                <a href="/medical/history" class="card-premium p-6 hover:shadow-md transition-shadow group">
                    <svg class="w-8 h-8 text-primary-600 mb-2 group-hover:scale-110 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"/></svg>
                    <p class="text-sm font-semibold text-slate-700">Mi historial medico</p>
                    <p class="text-xs text-slate-400">Consulta tus consultas previas</p>
                </a>
            </div>
        `;
    },

    // ============================================================
    // Grafica de ingresos (Chart.js via CDN)
    // ============================================================
    renderRevenueChart(data) {
        const canvas = document.getElementById('revenue-chart');
        if (!canvas || !data.length) return;

        // Cargar Chart.js dinamicamente
        if (typeof Chart === 'undefined') {
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js';
            script.onload = () => this._drawChart(canvas, data);
            document.head.appendChild(script);
        } else {
            this._drawChart(canvas, data);
        }
    },

    _drawChart(canvas, data) {
        new Chart(canvas, {
            type: 'bar',
            data: {
                labels: data.map(d => d.month),
                datasets: [{
                    label: 'Ingresos (MXN)',
                    data: data.map(d => d.revenue),
                    backgroundColor: '#6366f1',
                    borderRadius: 8,
                    borderSkipped: false,
                }],
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: false },
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { callback: (v) => '$' + v.toLocaleString() },
                    },
                },
            },
        });
    },

    formatMoney(n) {
        return Number(n).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    },
};

// Inicializar al cargar
document.addEventListener('DOMContentLoaded', () => DashboardView.init());
