/* ============================================================
   Cliente API - Wrapper de fetch para consumir el backend
   ============================================================ */

const Api = {
    /**
     * Realiza una peticion HTTP a la API.
     * Maneja cookies JWT automaticamente (same-origin).
     * @param {string} endpoint - Ruta relativa (ej: /api/auth/login)
     * @param {object} options - Opciones de fetch
     * @returns {Promise<object>} - Respuesta JSON
     */
    async request(endpoint, options = {}) {
        const defaults = {
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
        };
        const config = { ...defaults, ...options };
        if (config.body && typeof config.body === 'object') {
            config.body = JSON.stringify(config.body);
        }

        try {
            const response = await fetch(endpoint, config);
            const data = await response.json().catch(() => ({}));

            if (!response.ok) {
                const error = new Error(data.error || `Error ${response.status}`);
                error.status = response.status;
                error.payload = data;
                throw error;
            }
            return data;
        } catch (err) {
            // Errores de red
            if (err.status === undefined) {
                err.message = 'Error de conexion. Verifica tu red.';
            }
            // Token expirado o no autenticado
            if (err.status === 401) {
                AppAuth.redirectToLogin();
            }
            throw err;
        }
    },

    get(endpoint) {
        return this.request(endpoint, { method: 'GET' });
    },

    post(endpoint, body) {
        return this.request(endpoint, { method: 'POST', body });
    },

    patch(endpoint, body) {
        return this.request(endpoint, { method: 'PATCH', body });
    },

    delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    },

    /** Descarga un archivo binario (ej: PDF) */
    async download(endpoint) {
        const response = await fetch(endpoint, { credentials: 'same-origin' });
        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.error || 'Error al descargar');
        }
        return response.blob();
    },
};

/* ============================================================
   Endpoints agrupados por dominio
   ============================================================ */
const Endpoints = {
    auth: {
        login: '/api/auth/login',
        logout: '/api/auth/logout',
        register: '/api/auth/register',
        refresh: '/api/auth/refresh',
        me: '/api/auth/me',
    },
    appointments: {
        list: '/api/appointments',
        create: '/api/appointments',
        calendar: '/api/appointments/calendar',
        availability: (doctorId, date) =>
            `/api/appointments/doctors/${doctorId}/availability?date=${date}`,
        doctors: '/api/appointments/doctors',
        doctorDetail: (id) => `/api/appointments/doctors/${id}`,
        createDoctor: '/api/appointments/doctors',
    },
    medical: {
        createRecord: (aptId) => `/api/medical/appointments/${aptId}/record`,
        getRecord: (id) => `/api/medical/records/${id}`,
        getRecordByAppointment: (aptId) => `/api/medical/appointments/${aptId}/record`,
        patientHistory: (patientId) => `/api/medical/patients/${patientId}/history`,
        createPrescription: (recordId) => `/api/medical/records/${recordId}/prescriptions`,
        getPrescription: (code) => `/api/medical/prescriptions/${code}`,
        prescriptionPdf: (code) => `/api/medical/prescriptions/${code}/pdf`,
        patientPrescriptions: (patientId) => `/api/medical/patients/${patientId}/prescriptions`,
    },
    dashboard: '/api/dashboard',
};
