/* ============================================================
   Sidebar - Navegacion dinamica por rol
   ============================================================ */

const Sidebar = {
    /**
     * Items de navegacion por rol.
     * Cada item: { label, icon, href, roles }
     */
    items: [
        {
            label: 'Dashboard',
            icon: '<path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12l8.954-8.954a1.5 1.5 0 012.122 0L21.75 12M4.5 9.75v10.5a1.5 1.5 0 001.5 1.5H9m10.5-12v10.5a1.5 1.5 0 01-1.5 1.5h-3.75m-6 0h6m-6 0V9.75"/>',
            href: '/dashboard',
            roles: ['admin', 'medico', 'recepcionista', 'paciente'],
        },
        {
            label: 'Calendario',
            icon: '<path stroke-linecap="round" stroke-linejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0V11.25A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"/>',
            href: '/appointments/calendar',
            roles: ['admin', 'medico', 'recepcionista', 'paciente'],
        },
        {
            label: 'Mis Citas',
            icon: '<path stroke-linecap="round" stroke-linejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c1.036 0 1.875.84 1.875 1.875M18.75 8.25c1.036 0 1.875.84 1.875 1.875"/>',
            href: '/appointments',
            roles: ['admin', 'medico', 'recepcionista', 'paciente'],
        },
        {
            label: 'Sala de Espera',
            icon: '<path stroke-linecap="round" stroke-linejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z"/>',
            href: '/waiting-room',
            roles: ['recepcionista', 'admin'],
        },
        {
            label: 'Pacientes',
            icon: '<path stroke-linecap="round" stroke-linejoin="round" d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z"/>',
            href: '/patients',
            roles: ['recepcionista', 'admin', 'medico'],
        },
        {
            label: 'Expedientes',
            icon: '<path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"/>',
            href: '/medical/records',
            roles: ['medico', 'admin'],
        },
        {
            label: 'Recetas',
            icon: '<path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>',
            href: '/prescriptions',
            roles: ['medico', 'admin', 'paciente'],
        },
        {
            label: 'Personal',
            icon: '<path stroke-linecap="round" stroke-linejoin="round" d="M17.982 18.725A7.488 7.488 0 0012 15.75a7.488 7.488 0 00-5.982 2.975m11.963 0a9 9 0 10-11.963 0m11.963 0A8.966 8.966 0 0112 21a8.966 8.966 0 01-5.982-2.275M15 9.75a3 3 0 11-6 0 3 3 0 016 0z"/>',
            href: '/staff',
            roles: ['admin'],
        },
        {
            label: 'Reportes',
            icon: '<path stroke-linecap="round" stroke-linejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"/>',
            href: '/reports',
            roles: ['admin'],
        },
    ],

    /**
     * Construye el sidebar segun el rol del usuario.
     * @param {string} role - Rol del usuario
     */
    build(role) {
        const nav = document.getElementById('sidebar-nav');
        if (!nav) return;

        const currentPath = window.location.pathname;
        const filtered = this.items.filter(item => item.roles.includes(role));

        nav.innerHTML = filtered.map(item => {
            const isActive = currentPath === item.href ||
                (item.href !== '/dashboard' && currentPath.startsWith(item.href));
            const activeClass = isActive ? 'nav-item-active' : 'text-slate-600 hover:bg-slate-50';

            return `
                <a href="${item.href}"
                   class="flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm transition-all ${activeClass}">
                    <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                        ${item.icon}
                    </svg>
                    ${item.label}
                </a>`;
        }).join('');
    },
};

/* ============================================================
   Utilidades generales
   ============================================================ */
const Utils = {
    /** Toggle sidebar en mobile */
    toggleSidebar() {
        const sidebar = document.getElementById('sidebar');
        const overlay = document.getElementById('sidebar-overlay');
        if (sidebar) sidebar.classList.toggle('-translate-x-full');
        if (overlay) overlay.classList.toggle('hidden');
    },

    /** Formatea una fecha ISO a formato legible */
    formatDate(iso, withTime = true) {
        if (!iso) return '-';
        const d = new Date(iso);
        const opts = { year: 'numeric', month: 'short', day: 'numeric' };
        if (withTime) {
            opts.hour = '2-digit';
            opts.minute = '2-digit';
        }
        return d.toLocaleDateString('es-ES', opts);
    },

    /** Formatea solo la hora */
    formatTime(iso) {
        if (!iso) return '-';
        return new Date(iso).toLocaleTimeString('es-ES', {
            hour: '2-digit', minute: '2-digit'
        });
    },

    /** Clase CSS del badge segun estado de cita */
    statusBadge(status) {
        const map = {
            pendiente:    { class: 'badge-pending',       label: 'Pendiente' },
            confirmada:   { class: 'badge-confirmed',     label: 'Confirmada' },
            en_consulta:  { class: 'badge-in-consultation', label: 'En Consulta' },
            completada:   { class: 'badge-completed',     label: 'Completada' },
            cancelada:    { class: 'badge-cancelled',     label: 'Cancelada' },
        };
        const s = map[status] || { class: 'badge-pending', label: status };
        return `<span class="badge ${s.class}">${s.label}</span>`;
    },

    /** Inicializa el layout al cargar cualquier pagina protegida */
    initPage() {
        AppAuth.initLayout();
    },
};

// Inicializar layout en todas las paginas que usan base.html
document.addEventListener('DOMContentLoaded', () => Utils.initPage());
