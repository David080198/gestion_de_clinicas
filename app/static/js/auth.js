/* ============================================================
   Autenticacion - Gestiona sesion, login, logout y redirecciones
   ============================================================ */

const AppAuth = {
    /** Usuario actual cacheado */
    currentUser: null,

    /**
     * Obtiene el usuario actual desde /me.
     * @returns {Promise<object|null>}
     */
    async getCurrentUser() {
        if (this.currentUser) return this.currentUser;
        try {
            const data = await Api.get(Endpoints.auth.me);
            this.currentUser = data.user;
            return this.currentUser;
        } catch (err) {
            return null;
        }
    },

    /**
     * Inicia sesion.
     * @param {string} email
     * @param {string} password
     * @returns {Promise<object>} Usuario logueado
     */
    async login(email, password) {
        const data = await Api.post(Endpoints.auth.login, { email, password });
        this.currentUser = data.user;
        return data.user;
    },

    /**
     * Cierra sesion y redirige al login.
     */
    async logout() {
        try {
            await Api.post(Endpoints.auth.logout);
        } catch (e) {
            // ignorar errores de red al cerrar sesion
        }
        this.currentUser = null;
        this.redirectToLogin();
    },

    /**
     * Registra un nuevo paciente.
     */
    async register(payload) {
        const data = await Api.post(Endpoints.auth.register, payload);
        return data.user;
    },

    /**
     * Redirige al login si no hay sesion.
     */
    redirectToLogin() {
        if (!window.location.pathname.endsWith('/login')) {
            window.location.href = '/login';
        }
    },

    /**
     * Verifica si hay sesion activa; si no, redirige.
     * Usar en paginas protegidas.
     */
    async requireAuth() {
        const user = await this.getCurrentUser();
        if (!user) {
            this.redirectToLogin();
            return null;
        }
        return user;
    },

    /**
     * Verifica si el usuario tiene uno de los roles permitidos.
     * @param {string[]} roles - Roles permitidos
     * @returns {Promise<object|null>} Usuario si tiene permiso, null si no
     */
    async requireRole(roles) {
        const user = await this.requireAuth();
        if (!user) return null;
        if (!roles.includes(user.role)) {
            Toasts.error('No tienes permiso para acceder a esta pagina.');
            setTimeout(() => window.location.href = '/dashboard', 1500);
            return null;
        }
        return user;
    },

    /**
     * Inicializa el layout: carga el usuario y configura la UI.
     */
    async initLayout() {
        const user = await this.requireAuth();
        if (!user) return;

        // Actualizar perfil en sidebar
        const nameEl = document.getElementById('user-name');
        const roleEl = document.getElementById('user-role');
        const avatarEl = document.getElementById('user-avatar');
        if (nameEl) nameEl.textContent = user.full_name || user.email;
        if (roleEl) roleEl.textContent = this.roleLabel(user.role);
        if (avatarEl) avatarEl.textContent = (user.first_name || user.email || '?')[0].toUpperCase();

        // Construir sidebar segun rol
        Sidebar.build(user.role);

        // Fecha actual en header
        const dateEl = document.getElementById('current-date');
        if (dateEl) {
            const now = new Date();
            dateEl.textContent = now.toLocaleDateString('es-ES', {
                weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
            });
        }
    },

    /**
     * Etiqueta legible del rol.
     */
    roleLabel(role) {
        const labels = {
            admin: 'Administrador',
            medico: 'Medico',
            recepcionista: 'Recepcionista',
            paciente: 'Paciente',
        };
        return labels[role] || role;
    },
};

/* ============================================================
   Atajos de acciones de autenticacion para botones
   ============================================================ */
const AuthActions = {
    logout: () => AppAuth.logout(),
};
