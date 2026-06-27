/* ============================================================
   Formulario de nueva cita - Seleccion de medico, fecha y slot
   ============================================================ */

const AppointmentForm = {
    user: null,
    doctors: [],
    selectedDoctor: null,
    selectedSlot: null,

    async init() {
        this.user = await AppAuth.requireAuth();
        if (!this.user) return;

        // Pacientes solo pueden agendar para si mismos
        if (this.user.role !== 'paciente' && this.user.role !== 'recepcionista' && this.user.role !== 'admin') {
            Toasts.error('No tienes permiso para agendar citas');
            setTimeout(() => window.location.href = '/dashboard', 1500);
            return;
        }

        await this.loadDoctors();

        // Preseleccionar fecha desde query param
        const params = new URLSearchParams(window.location.search);
        const dateParam = params.get('date');
        if (dateParam) {
            document.getElementById('appointment-date').value = dateParam;
        }

        // Si es paciente, precargar su patient_id
        if (this.user.role === 'paciente' && this.user.patient_profile) {
            // se usara automaticamente en el submit
        }
    },

    async loadDoctors() {
        try {
            const data = await Api.get(Endpoints.appointments.doctors);
            this.doctors = data.items || [];
            const select = document.getElementById('doctor-select');

            this.doctors.forEach(doc => {
                const opt = document.createElement('option');
                opt.value = doc.id;
                opt.textContent = `${doc.full_name} - ${doc.specialty}`;
                select.appendChild(opt);
            });
        } catch (err) {
            Toasts.error('Error al cargar medicos: ' + err.message);
        }
    },

    onDoctorChange() {
        const id = parseInt(document.getElementById('doctor-select').value);
        this.selectedDoctor = this.doctors.find(d => d.id === id);
        this.selectedSlot = null;

        const info = document.getElementById('doctor-info');
        if (!this.selectedDoctor) {
            info.classList.add('hidden');
            return;
        }

        info.classList.remove('hidden');
        document.getElementById('doctor-avatar').textContent = this.selectedDoctor.full_name[0];
        document.getElementById('doctor-name').textContent = this.selectedDoctor.full_name;
        document.getElementById('doctor-specialty').textContent = this.selectedDoctor.specialty;
        document.getElementById('doctor-fee').textContent = '$' + this.selectedDoctor.consultation_fee;

        // Si ya hay fecha, cargar slots
        const date = document.getElementById('appointment-date').value;
        if (date) this.onDateChange();
    },

    async onDateChange() {
        const date = document.getElementById('appointment-date').value;
        const doctorId = this.selectedDoctor?.id;

        const section = document.getElementById('slots-section');
        const container = document.getElementById('slots-container');
        const submitBtn = document.getElementById('submit-btn');

        if (!date || !doctorId) {
            section.classList.add('hidden');
            submitBtn.disabled = true;
            return;
        }

        section.classList.remove('hidden');
        container.innerHTML = '<div class="skeleton h-10 rounded-lg col-span-4"></div><div class="skeleton h-10 rounded-lg col-span-2"></div>';

        try {
            const data = await Api.get(Endpoints.appointments.availability(doctorId, date));
            const slots = data.slots || [];
            const available = slots.filter(s => s.available);

            if (available.length === 0) {
                container.innerHTML = '<p class="col-span-full text-center text-slate-400 text-sm py-4">No hay horarios disponibles para esta fecha</p>';
                submitBtn.disabled = true;
                return;
            }

            container.innerHTML = available.map(s => {
                const time = s.start.split('T')[1].substring(0, 5);
                return `<button type="button" onclick="AppointmentForm.selectSlot('${s.start}','${s.end}', this)"
                    class="px-3 py-2 rounded-lg border border-slate-200 text-sm font-medium text-slate-700 hover:border-primary-400 hover:bg-primary-50 transition-all slot-btn">
                    ${time}
                </button>`;
            }).join('');
        } catch (err) {
            container.innerHTML = `<p class="col-span-full text-center text-red-500 text-sm py-4">${err.message}</p>`;
        }
    },

    selectSlot(start, end, btn) {
        this.selectedSlot = { start, end };
        // Resaltar boton seleccionado
        document.querySelectorAll('.slot-btn').forEach(b => {
            b.classList.remove('border-primary-500', 'bg-primary-100', 'text-primary-700');
        });
        btn.classList.add('border-primary-500', 'bg-primary-100', 'text-primary-700');
        document.getElementById('submit-btn').disabled = false;
    },

    async submit() {
        if (!this.selectedDoctor || !this.selectedSlot) {
            Toasts.warning('Selecciona medico y horario');
            return;
        }

        const btn = document.getElementById('submit-btn');
        const text = document.getElementById('submit-text');
        const spinner = document.getElementById('submit-spinner');
        btn.disabled = true;
        text.textContent = 'Agendando...';
        spinner.classList.remove('hidden');

        // Construir payload
        const payload = {
            doctor_id: this.selectedDoctor.id,
            start_time: this.selectedSlot.start,
            end_time: this.selectedSlot.end,
            reason: document.getElementById('reason').value || null,
        };

        // patient_id depende del rol
        if (this.user.role === 'paciente') {
            // El backend usara el patient_id del usuario; pero el schema lo requiere
            payload.patient_id = this.user.patient_profile?.id || 0;
        } else {
            // recepcionista/admin: deben seleccionar un paciente
            // Por simplicidad, se pedira el patient_id via prompt
            const pid = document.getElementById('patient-id')?.value;
            if (!pid) {
                Toasts.error('Selecciona un paciente');
                btn.disabled = false;
                text.textContent = 'Agendar cita';
                spinner.classList.add('hidden');
                return;
            }
            payload.patient_id = parseInt(pid);
        }

        try {
            const data = await Api.post(Endpoints.appointments.create, payload);
            Toasts.success('Cita agendada correctamente');
            setTimeout(() => window.location.href = `/appointments/${data.appointment.id}`, 800);
        } catch (err) {
            Toasts.error(err.message);
            btn.disabled = false;
            text.textContent = 'Agendar cita';
            spinner.classList.add('hidden');
        }
    },
};

document.addEventListener('DOMContentLoaded', () => {
    AppointmentForm.init();
    document.getElementById('appointment-form')?.addEventListener('submit', (e) => {
        e.preventDefault();
        AppointmentForm.submit();
    });
});
