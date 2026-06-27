/* ============================================================
   Consulta medica - Formulario del expediente clinico + receta
   ============================================================ */

const ConsultView = {
    appointmentId: null,
    appointment: null,
    user: null,
    existingRecord: null,

    async init() {
        this.user = await AppAuth.requireRole(['medico', 'admin']);
        if (!this.user) return;

        // Extraer ID de la cita desde la URL
        const parts = window.location.pathname.split('/');
        this.appointmentId = parts[parts.length - 1];

        await this.loadAppointment();
    },

    async loadAppointment() {
        try {
            const data = await Api.get(`${Endpoints.appointments.list}/${this.appointmentId}`);
            this.appointment = data.appointment;

            // Verificar si ya existe expediente
            try {
                const recData = await Api.get(Endpoints.medical.getRecordByAppointment(this.appointmentId));
                this.existingRecord = recData.record;
            } catch (e) {
                this.existingRecord = null;
            }

            this.render();
        } catch (err) {
            Toasts.error('Error al cargar la cita: ' + err.message);
        }
    },

    render() {
        document.getElementById('loading').classList.add('hidden');
        const content = document.getElementById('consult-content');
        content.classList.remove('hidden');
        content.classList.add('animate-fade-in');

        const a = this.appointment;
        const hasRecord = this.existingRecord !== null;

        content.innerHTML = `
            <!-- Info de la cita -->
            <div class="card-premium p-6">
                <div class="flex items-center justify-between mb-4">
                    <div>
                        <h2 class="text-xl font-bold text-slate-800">Consulta medica</h2>
                        <p class="text-sm text-slate-500">Cita #${a.id}</p>
                    </div>
                    ${Utils.statusBadge(a.status)}
                </div>
                <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div><p class="text-slate-400 text-xs">Paciente</p><p class="font-semibold text-slate-800">${a.patient_name}</p></div>
                    <div><p class="text-slate-400 text-xs">Fecha</p><p class="font-semibold text-slate-800">${Utils.formatDate(a.start_time)}</p></div>
                    <div><p class="text-slate-400 text-xs">Hora</p><p class="font-semibold text-slate-800">${Utils.formatTime(a.start_time)}</p></div>
                    <div><p class="text-slate-400 text-xs">Motivo</p><p class="font-semibold text-slate-800">${a.reason || '-'}</p></div>
                </div>
            </div>

            ${hasRecord ? this.renderExistingRecord() : this.renderRecordForm()}
        `;

        if (!hasRecord) {
            this.attachFormHandlers();
        }
    },

    // ============================================================
    // Formulario de nuevo expediente
    // ============================================================
    renderRecordForm() {
        const canCreate = this.appointment.status === 'en_consulta' || this.appointment.status === 'completada';

        if (!canCreate) {
            return `
                <div class="card-premium p-8 text-center">
                    <svg class="w-12 h-12 text-amber-400 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.008v.008H12v-.008z"/></svg>
                    <p class="text-slate-700 font-semibold mb-1">La cita debe estar EN CONSULTA para crear el expediente</p>
                    <p class="text-sm text-slate-500 mb-4">Cambia el estado a "En Consulta" para comenzar a llenar el expediente</p>
                    ${this.appointment.status === 'confirmada' ? `
                        <button onclick="ConsultView.startConsultation()" class="btn-primary">Iniciar consulta</button>
                    ` : ''}
                </div>
            `;
        }

        return `
            <form id="record-form" class="space-y-6">

                <!-- Motivo y sintomas -->
                <div class="card-premium p-6">
                    <h3 class="text-lg font-bold text-slate-800 mb-4">Motivo y sintomas</h3>
                    <div class="space-y-4">
                        <div>
                            <label class="block text-sm font-semibold text-slate-700 mb-1.5">Motivo de la visita</label>
                            <input type="text" id="reason" class="input-premium" value="${this.appointment.reason || ''}">
                        </div>
                        <div>
                            <label class="block text-sm font-semibold text-slate-700 mb-1.5">Sintomas reportados</label>
                            <textarea id="symptoms" rows="3" class="input-premium" placeholder="Describe los sintomas que reporta el paciente..."></textarea>
                        </div>
                    </div>
                </div>

                <!-- Signos vitales -->
                <div class="card-premium p-6">
                    <h3 class="text-lg font-bold text-slate-800 mb-4">Signos vitales</h3>
                    <div class="grid grid-cols-2 md:grid-cols-5 gap-4">
                        <div>
                            <label class="block text-xs font-semibold text-slate-600 mb-1">Presion arterial</label>
                            <input type="text" id="blood_pressure" class="input-premium" placeholder="120/80">
                        </div>
                        <div>
                            <label class="block text-xs font-semibold text-slate-600 mb-1">Temp. (C)</label>
                            <input type="number" step="0.1" id="temperature" class="input-premium" placeholder="36.5">
                        </div>
                        <div>
                            <label class="block text-xs font-semibold text-slate-600 mb-1">Ritmo (bpm)</label>
                            <input type="number" id="heart_rate" class="input-premium" placeholder="72">
                        </div>
                        <div>
                            <label class="block text-xs font-semibold text-slate-600 mb-1">Peso (kg)</label>
                            <input type="number" step="0.1" id="weight" class="input-premium" placeholder="75.0">
                        </div>
                        <div>
                            <label class="block text-xs font-semibold text-slate-600 mb-1">Talla (cm)</label>
                            <input type="number" step="0.1" id="height" class="input-premium" placeholder="170">
                        </div>
                    </div>
                </div>

                <!-- Diagnostico y tratamiento -->
                <div class="card-premium p-6">
                    <h3 class="text-lg font-bold text-slate-800 mb-4">Diagnostico y tratamiento</h3>
                    <div class="space-y-4">
                        <div>
                            <label class="block text-sm font-semibold text-slate-700 mb-1.5">Diagnostico / Notas de evolucion</label>
                            <textarea id="diagnosis" rows="4" class="input-premium" placeholder="Diagnostico clinico, notas de evolucion, observaciones..."></textarea>
                        </div>
                        <div>
                            <label class="block text-sm font-semibold text-slate-700 mb-1.5">Tratamiento sugerido</label>
                            <textarea id="treatment" rows="3" class="input-premium" placeholder="Indicaciones terapeuticas, medicamentos, medidas generales..."></textarea>
                        </div>
                        <div>
                            <label class="block text-sm font-semibold text-slate-700 mb-1.5">Notas adicionales</label>
                            <textarea id="notes" rows="2" class="input-premium" placeholder="Notas internas para el expediente..."></textarea>
                        </div>
                    </div>
                </div>

                <!-- Guardar expediente -->
                <div class="flex gap-3">
                    <button type="button" onclick="ConsultView.saveRecord()" id="save-record-btn" class="btn-primary flex-1 justify-center">
                        <span id="save-text">Guardar expediente</span>
                        <div id="save-spinner" class="spinner hidden"></div>
                    </button>
                    <button type="button" onclick="ConsultView.completeAppointment()" class="btn-secondary">
                        Completar cita
                    </button>
                </div>
            </form>
        `;
    },

    attachFormHandlers() {},

    async startConsultation() {
        try {
            await Api.patch(`${Endpoints.appointments.list}/${this.appointmentId}/status`, { status: 'en_consulta' });
            Toasts.success('Consulta iniciada');
            await this.loadAppointment();
        } catch (err) {
            Toasts.error(err.message);
        }
    },

    async saveRecord() {
        const btn = document.getElementById('save-record-btn');
        const text = document.getElementById('save-text');
        const spinner = document.getElementById('save-spinner');
        btn.disabled = true; text.textContent = 'Guardando...'; spinner.classList.remove('hidden');

        const payload = {
            reason: document.getElementById('reason').value || null,
            symptoms: document.getElementById('symptoms').value || null,
            blood_pressure: document.getElementById('blood_pressure').value || null,
            temperature: parseFloat(document.getElementById('temperature').value) || null,
            heart_rate: parseInt(document.getElementById('heart_rate').value) || null,
            weight: parseFloat(document.getElementById('weight').value) || null,
            height: parseFloat(document.getElementById('height').value) || null,
            diagnosis: document.getElementById('diagnosis').value || null,
            treatment: document.getElementById('treatment').value || null,
            notes: document.getElementById('notes').value || null,
        };

        try {
            const data = await Api.post(Endpoints.medical.createRecord(this.appointmentId), payload);
            Toasts.success('Expediente guardado (inmutable)');
            this.existingRecord = data.record;
            this.render();
        } catch (err) {
            Toasts.error(err.message);
            btn.disabled = false; text.textContent = 'Guardar expediente'; spinner.classList.add('hidden');
        }
    },

    async completeAppointment() {
        try {
            await Api.patch(`${Endpoints.appointments.list}/${this.appointmentId}/status`, { status: 'completada' });
            Toasts.success('Cita completada');
            window.location.href = '/dashboard';
        } catch (err) {
            Toasts.error(err.message);
        }
    },

    // ============================================================
    // Expediente ya existente (lectura + receta)
    // ============================================================
    renderExistingRecord() {
        const r = this.existingRecord;
        return `
            <!-- Expediente guardado (solo lectura) -->
            <div class="card-premium p-6">
                <div class="flex items-center gap-2 mb-4">
                    <svg class="w-5 h-5 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                    <h3 class="text-lg font-bold text-slate-800">Expediente guardado</h3>
                    <span class="text-xs text-slate-400 ml-auto">Inmutable - ${Utils.formatDate(r.created_at)}</span>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div class="space-y-3">
                        <div><p class="text-xs text-slate-400">Motivo</p><p class="text-sm text-slate-800">${r.reason || '-'}</p></div>
                        <div><p class="text-xs text-slate-400">Sintomas</p><p class="text-sm text-slate-800">${r.symptoms || '-'}</p></div>
                        <div><p class="text-xs text-slate-400">Diagnostico</p><p class="text-sm text-slate-800">${r.diagnosis || '-'}</p></div>
                        <div><p class="text-xs text-slate-400">Tratamiento</p><p class="text-sm text-slate-800">${r.treatment || '-'}</p></div>
                    </div>
                    <div class="bg-slate-50 rounded-xl p-4">
                        <p class="text-xs font-bold text-slate-500 uppercase mb-3">Signos vitales</p>
                        <div class="grid grid-cols-2 gap-3 text-sm">
                            <div><p class="text-slate-400 text-xs">Presion</p><p class="font-semibold">${r.blood_pressure || '-'}</p></div>
                            <div><p class="text-slate-400 text-xs">Temp.</p><p class="font-semibold">${r.temperature || '-'} C</p></div>
                            <div><p class="text-slate-400 text-xs">Ritmo</p><p class="font-semibold">${r.heart_rate || '-'} bpm</p></div>
                            <div><p class="text-slate-400 text-xs">Peso</p><p class="font-semibold">${r.weight || '-'} kg</p></div>
                            <div><p class="text-slate-400 text-xs">Talla</p><p class="font-semibold">${r.height || '-'} cm</p></div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Recetas -->
            <div class="card-premium p-6">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-lg font-bold text-slate-800">Recetas electronicas</h3>
                    <button onclick="ConsultView.showPrescriptionForm()" class="btn-primary text-sm">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15"/></svg>
                        Emitir receta
                    </button>
                </div>
                <div id="prescriptions-list">
                    <p class="text-slate-400 text-sm text-center py-4">No hay recetas emitidas para esta consulta</p>
                </div>
            </div>

            <!-- Modal de receta -->
            <div id="rx-modal" class="modal-overlay hidden" onclick="ConsultView.closeRxModal(event)">
                <div class="modal-content p-6" onclick="event.stopPropagation()">
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="text-lg font-bold text-slate-800">Emitir receta medica</h3>
                        <button onclick="ConsultView.closeRxModal()" class="text-slate-400 hover:text-slate-600">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
                        </button>
                    </div>
                    <form id="rx-form" class="space-y-4">
                        <div id="medications-container" class="space-y-3">
                            <!-- Medicamentos dinamicos -->
                        </div>
                        <button type="button" onclick="ConsultView.addMedication()" class="btn-secondary text-sm w-full justify-center">
                            + Agregar medicamento
                        </button>
                        <div>
                            <label class="block text-sm font-semibold text-slate-700 mb-1.5">Indicaciones generales</label>
                            <textarea id="rx-notes" rows="2" class="input-premium" placeholder="Ej: Suspender si aparece rash..."></textarea>
                        </div>
                        <button type="button" onclick="ConsultView.savePrescription()" class="btn-primary w-full justify-center">
                            Emitir receta
                        </button>
                    </form>
                </div>
            </div>
        `;
    },

    // ============================================================
    // Receta - medicamentos dinamicos
    // ============================================================
    showPrescriptionForm() {
        document.getElementById('rx-modal').classList.remove('hidden');
        document.getElementById('medications-container').innerHTML = '';
        this.addMedication();
    },

    closeRxModal(event) {
        if (event && event.target !== event.currentTarget) return;
        document.getElementById('rx-modal').classList.add('hidden');
    },

    addMedication() {
        const container = document.getElementById('medications-container');
        const idx = container.children.length;
        const div = document.createElement('div');
        div.className = 'border border-slate-200 rounded-xl p-4 space-y-2';
        div.innerHTML = `
            <div class="flex items-center justify-between">
                <p class="text-xs font-bold text-slate-500">Medicamento #${idx + 1}</p>
                <button type="button" onclick="this.closest('.border-slate-200').remove()" class="text-red-400 hover:text-red-600 text-xs">Eliminar</button>
            </div>
            <input type="text" placeholder="Nombre del medicamento *" class="input-premium med-name" required>
            <div class="grid grid-cols-3 gap-2">
                <input type="text" placeholder="Dosis (500mg)" class="input-premium med-dose text-sm">
                <input type="text" placeholder="Frecuencia (c/8h)" class="input-premium med-freq text-sm">
                <input type="text" placeholder="Duracion (5 dias)" class="input-premium med-dur text-sm">
            </div>
            <input type="text" placeholder="Indicaciones (con alimentos...)" class="input-premium med-instr text-sm">
        `;
        container.appendChild(div);
    },

    async savePrescription() {
        const meds = [];
        document.querySelectorAll('#medications-container > div').forEach(div => {
            const name = div.querySelector('.med-name').value.trim();
            if (name) {
                meds.push({
                    name,
                    dose: div.querySelector('.med-dose').value || null,
                    frequency: div.querySelector('.med-freq').value || null,
                    duration: div.querySelector('.med-dur').value || null,
                    instructions: div.querySelector('.med-instr').value || null,
                });
            }
        });

        if (meds.length === 0) {
            Toasts.warning('Agrega al menos un medicamento');
            return;
        }

        const payload = {
            medications: meds,
            notes: document.getElementById('rx-notes').value || null,
        };

        try {
            await Api.post(Endpoints.medical.createPrescription(this.existingRecord.id), payload);
            Toasts.success('Receta emitida correctamente');
            this.closeRxModal();
            await this.loadPrescriptions();
        } catch (err) {
            Toasts.error(err.message);
        }
    },

    async loadPrescriptions() {
        // Por simplicidad, recargar la pagina para mostrar la receta
        // En una implementacion completa, se consultaria el endpoint de recetas del expediente
        Toasts.info('Recarga para ver la receta emitida');
    },
};

document.addEventListener('DOMContentLoaded', () => ConsultView.init());
