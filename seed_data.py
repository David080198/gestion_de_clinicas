"""Seed completo: super-admin + clinica demo + usuarios + data + suscripcion."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from app import create_app
from app.extensions import db
from app.models import (
    Appointment, AppointmentStatus, BloodType, BillingCycle, Clinic,
    ClinicPlan, ClinicStatus, Doctor, DoctorSchedule, Gender, Invoice,
    InvoiceStatus, MedicalRecord, Patient, Payment, PaymentMethod,
    BillingPaymentStatus, Prescription, Subscription, SubscriptionStatus,
    User, UserRole, Weekday,
)

UTC = timezone.utc


def _symptoms(reason):
    s = {
        "Dolor de cabeza persistente": "Cefalea bilateral, pulsatil, 3 dias de evolucion. Fotofobia leve.",
        "Consulta pediatrica de rutina": "Paciente asintomatico. Control de crecimiento y desarrollo.",
        "Control de hipertension": "Asintomatico. Toma de presion domiciliaria elevada en ultimas 2 semanas.",
        "Dolor abdominal": "Dolor en cuadrante inferior derecho, 48h de evolucion. Nauseas matutinas.",
        "Fiebre y tos": "Fiebre 38.5C, tos seca, 4 dias. Sin disnea. Astenia.",
        "Consulta de seguimiento": "Mejoria parcial tras tratamiento previo. Sin nuevos sintomas.",
        "Revision de resultados": "Resultados de laboratorio: glucemia elevada. Asintomatico.",
        "Migrana recurrente": "Cefalea hemicraneal derecha, pulsatil, con aura visual previo.",
    }
    return s.get(reason, "Sintomas generales. Evaluacion en curso.")


def _diagnosis(reason):
    d = {
        "Dolor de cabeza persistente": "Cefalea tensional episodica",
        "Consulta pediatrica de rutina": "Paciente sano. Desarrollo normal para la edad.",
        "Control de hipertension": "Hipertension arterial grado 1, controlada",
        "Dolor abdominal": "Gastroenteritis aguda",
        "Fiebre y tos": "Infeccion respiratoria alta",
        "Consulta de seguimiento": "Evolucion favorable",
        "Revision de resultados": "Prediabetes. Indicar cambios en estilo de vida.",
        "Migrana recurrente": "Migrana con aura, episodica",
    }
    return d.get(reason, "Diagnostico en evaluacion.")


def _treatment(reason):
    t = {
        "Dolor de cabeza persistente": "Paracetamol 500mg c/8h, hidratacion, reposo.",
        "Consulta pediatrica de rutina": "Continuar esquema de vacunacion. Dieta balanceada.",
        "Control de hipertension": "Continuar Losartan 50mg. Reducir sodio. Ejercicio 30min/dia.",
        "Dolor abdominal": "Dieta blanda, hidratacion oral. Metoclopramida 10mg SI nausea.",
        "Fiebre y tos": "Paracetamol 500mg c/6h por fiebre. Hidratacion. Reposo 3 dias.",
        "Consulta de seguimiento": "Continuar tratamiento. Control en 1 mes.",
        "Revision de resultados": "Dieta baja en carbohidratos. Ejercicio aerobico 150min/semana.",
        "Migrana recurrente": "Sumatriptan 50mg al inicio del aura. Profilaxis con Propranolol 40mg/dia.",
    }
    return t.get(reason, "Tratamiento sintomatico. Control en 2 semanas.")


def _medications(reason):
    m = {
        "Dolor de cabeza persistente": [
            {"name": "Paracetamol", "dose": "500mg", "frequency": "c/8h", "duration": "5 dias", "instructions": "Via oral con agua"},
        ],
        "Control de hipertension": [
            {"name": "Losartan", "dose": "50mg", "frequency": "1 vez al dia", "duration": "Uso prolongado", "instructions": "Manana con desayuno"},
            {"name": "Hidroclorotiazida", "dose": "25mg", "frequency": "1 vez al dia", "duration": "Uso prolongado", "instructions": "Manana"},
        ],
        "Fiebre y tos": [
            {"name": "Paracetamol", "dose": "500mg", "frequency": "c/6h", "duration": "3 dias", "instructions": "Solo si fiebre > 38C"},
            {"name": "Ambroxol", "dose": "30mg", "frequency": "c/8h", "duration": "5 dias", "instructions": "Despues de comidas"},
        ],
        "Migrana recurrente": [
            {"name": "Sumatriptan", "dose": "50mg", "frequency": "al inicio del aura", "duration": "1 dosis", "instructions": "Via oral. Max 2 dosis/dia"},
            {"name": "Propranolol", "dose": "40mg", "frequency": "1 vez al dia", "duration": "3 meses", "instructions": "Profilaxis"},
        ],
    }
    return m.get(reason, [{"name": "Paracetamol", "dose": "500mg", "frequency": "c/8h", "duration": "3 dias", "instructions": "Via oral"}])


def run():
    app = create_app()
    with app.app_context():
        db.create_all()

        # ============================================================
        # 1. SUPER-ADMIN (sin clinica)
        # ============================================================
        sa = User.query.filter_by(email="super@medcenter.app").first()
        if not sa:
            sa = User(email="super@medcenter.app", first_name="Super", last_name="Admin",
                      role=UserRole.ADMIN, clinic_id=None)
            sa.set_password("Super123!")
            db.session.add(sa)
            print("[SEED] Super-admin creado: super@medcenter.app")

        # ============================================================
        # 2. CLINICA DEMO
        # ============================================================
        clinic = Clinic.query.filter_by(subdomain="demo").first()
        if not clinic:
            clinic = Clinic(
                name="MedCenter Demo", slug="demo", subdomain="demo",
                plan=ClinicPlan.PROFESSIONAL, status=ClinicStatus.ACTIVA,
                email="info@medcenterdemo.com", phone="555-1234",
                address="Av. Reforma 123, CDMX", timezone="America/Mexico_City", currency="MXN",
            )
            db.session.add(clinic)
            db.session.flush()
            print(f"[SEED] Clinica demo creada (id={clinic.id})")
        clinic_id = clinic.id

        # ============================================================
        # 3. SUSCRIPCION DE LA CLINICA
        # ============================================================
        sub = Subscription.query.filter_by(clinic_id=clinic_id).first()
        if not sub:
            now = datetime.now(UTC)
            sub = Subscription(
                clinic_id=clinic_id, plan=ClinicPlan.PROFESSIONAL,
                billing_cycle=BillingCycle.MENSUAL, status=SubscriptionStatus.ACTIVA,
                started_at=now - timedelta(days=30),
                current_period_start=now - timedelta(days=5),
                current_period_end=now + timedelta(days=25),
                auto_renew=True,
            )
            db.session.add(sub)
            db.session.flush()
            # Factura pagada
            inv = Invoice(
                subscription_id=sub.id, clinic_id=clinic_id,
                amount=3500.0, currency="MXN", status=InvoiceStatus.PAGADA,
                period_start=now - timedelta(days=5), period_end=now + timedelta(days=25),
                issue_date=now - timedelta(days=5), due_date=now - timedelta(days=5),
                paid_date=now - timedelta(days=5),
            )
            db.session.add(inv)
            db.session.flush()
            pay = Payment(
                invoice_id=inv.id, amount=3500.0, currency="MXN",
                method=PaymentMethod.MANUAL, status=BillingPaymentStatus.COMPLETADO,
                processed_at=now - timedelta(days=5),
            )
            db.session.add(pay)
            print("[SEED] Suscripcion activa + factura pagada ($3,500)")

        # ============================================================
        # 4. USUARIOS DE LA CLINICA
        # ============================================================
        users_data = [
            ("admin@medcenter.com", "Ana", "Administradora", UserRole.ADMIN, "Admin123!"),
            ("dr.house@medcenter.com", "Gregory", "House", UserRole.MEDICO, "Medico123!"),
            ("dra.grey@medcenter.com", "Meredith", "Grey", UserRole.MEDICO, "Medico123!"),
            ("recep@medcenter.com", "Maria", "Gonzalez", UserRole.RECEPCIONISTA, "Recep123!"),
        ]
        for email, fn, ln, role, pwd in users_data:
            u = User.query.filter_by(email=email).first()
            if not u:
                u = User(email=email, first_name=fn, last_name=ln, role=role, clinic_id=clinic_id)
                u.set_password(pwd)
                db.session.add(u)
                print(f"[SEED] Usuario creado: {email} ({role.value})")

        db.session.flush()

        # ============================================================
        # 5. MEDICOS
        # ============================================================
        med1 = User.query.filter_by(email="dr.house@medcenter.com").first()
        med2 = User.query.filter_by(email="dra.grey@medcenter.com").first()
        recep = User.query.filter_by(email="recep@medcenter.com").first()

        doc1 = Doctor.query.filter_by(user_id=med1.id).first()
        if not doc1:
            doc1 = Doctor(user_id=med1.id, clinic_id=clinic_id, license_number="MED-001",
                          specialty="Medicina Interna", consultation_fee=800,
                          bio="Especialista en diagnostico diferencial.")
            db.session.add(doc1)
            db.session.flush()
            for d in [Weekday.LUNES, Weekday.MARTES, Weekday.MIERCOLES, Weekday.JUEVES, Weekday.VIERNES]:
                db.session.add(DoctorSchedule(doctor_id=doc1.id, weekday=d,
                                              start_time=time(9, 0), end_time=time(18, 0), slot_minutes=30))
            print("[SEED] Dr. House configurado (Lun-Vie 09-18)")

        doc2 = Doctor.query.filter_by(user_id=med2.id).first()
        if not doc2:
            doc2 = Doctor(user_id=med2.id, clinic_id=clinic_id, license_number="MED-002",
                          specialty="Pediatria", consultation_fee=600,
                          bio="Pediatra con 10 anos de experiencia.")
            db.session.add(doc2)
            db.session.flush()
            for d in [Weekday.LUNES, Weekday.MIERCOLES, Weekday.VIERNES]:
                db.session.add(DoctorSchedule(doctor_id=doc2.id, weekday=d,
                                              start_time=time(10, 0), end_time=time(14, 0), slot_minutes=30))
            print("[SEED] Dra. Grey configurada (Lun-Mie-Vie 10-14)")

        # ============================================================
        # 6. PACIENTES
        # ============================================================
        pats_data = [
            ("juan@paciente.com", "Juan", "Perez", "DOC123", date(1990, 5, 15), Gender.MASCULINO, BloodType.O_POS, "Penicilina"),
            ("lucia@paciente.com", "Lucia", "Martinez", "DOC456", date(1985, 8, 22), Gender.FEMENINO, BloodType.A_POS, None),
            ("carlos@paciente.com", "Carlos", "Ramirez", "DOC789", date(1975, 3, 10), Gender.MASCULINO, BloodType.B_POS, "Aspirina"),
            ("sofia@paciente.com", "Sofia", "Lopez", "DOC012", date(1995, 11, 25), Gender.FEMENINO, BloodType.A_NEG, None),
            ("pedro@paciente.com", "Pedro", "Ruiz", "DOC345", date(1988, 7, 18), Gender.MASCULINO, BloodType.O_NEG, "Mariscos"),
        ]
        all_pats = []
        for email, fn, ln, doc_num, bday, gender, bt, allergies in pats_data:
            u = User.query.filter_by(email=email).first()
            if not u:
                u = User(email=email, first_name=fn, last_name=ln, role=UserRole.PACIENTE, clinic_id=clinic_id)
                u.set_password("Secret123")
                db.session.add(u)
                db.session.flush()
                p = Patient(user_id=u.id, clinic_id=clinic_id, document_number=doc_num,
                            birth_date=bday, gender=gender, blood_type=bt, allergies=allergies,
                            address="Ciudad de Mexico", emergency_contact_name="Familiar",
                            emergency_contact_phone="555-1234")
                db.session.add(p)
                db.session.flush()
                all_pats.append(p)
                print(f"[SEED] Paciente creado: {fn} {ln}")
            else:
                p = Patient.query.filter_by(user_id=u.id).first()
                if p:
                    all_pats.append(p)

        juan, lucia, carlos, sofia, pedro = all_pats[0], all_pats[1], all_pats[2], all_pats[3], all_pats[4]

        # ============================================================
        # 7. CITAS PASADAS + EXPEDIENTES + RECETAS
        # ============================================================
        today = date.today()
        days_to_monday = (7 - today.weekday()) % 7
        if days_to_monday == 0:
            days_to_monday = 7
        next_monday = today + timedelta(days=days_to_monday)
        past_monday = next_monday - timedelta(days=14)

        past_appts = [
            (juan, doc1, past_monday, 9, 0, 30, AppointmentStatus.COMPLETADA, "Dolor de cabeza persistente"),
            (lucia, doc2, past_monday, 10, 0, 30, AppointmentStatus.COMPLETADA, "Consulta pediatrica de rutina"),
            (carlos, doc1, past_monday + timedelta(days=2), 9, 30, 30, AppointmentStatus.COMPLETADA, "Control de hipertension"),
            (sofia, doc1, past_monday + timedelta(days=2), 11, 0, 30, AppointmentStatus.COMPLETADA, "Dolor abdominal"),
            (pedro, doc2, past_monday + timedelta(days=4), 10, 0, 30, AppointmentStatus.COMPLETADA, "Fiebre y tos"),
            (juan, doc2, past_monday + timedelta(days=7), 10, 30, 30, AppointmentStatus.COMPLETADA, "Consulta de seguimiento"),
            (carlos, doc1, past_monday + timedelta(days=7), 9, 0, 30, AppointmentStatus.COMPLETADA, "Revision de resultados"),
            (lucia, doc1, past_monday + timedelta(days=9), 14, 0, 30, AppointmentStatus.COMPLETADA, "Migrana recurrente"),
        ]

        past_count = 0
        for pat, doc, appt_date, h, m, dur, status, reason in past_appts:
            start = datetime.combine(appt_date, time(h, m), tzinfo=UTC)
            end = start + timedelta(minutes=dur)
            if not Appointment.query.filter_by(doctor_id=doc.id, start_time=start).first():
                apt = Appointment(patient_id=pat.id, doctor_id=doc.id, receptionist_id=recep.id,
                                  clinic_id=clinic_id, start_time=start, end_time=end,
                                  status=status, reason=reason)
                db.session.add(apt)
                db.session.flush()
                past_count += 1
                if status == AppointmentStatus.COMPLETADA:
                    record = MedicalRecord(
                        appointment_id=apt.id, patient_id=pat.id, doctor_id=doc.id, clinic_id=clinic_id,
                        reason=reason, symptoms=_symptoms(reason), blood_pressure="120/80",
                        temperature=round(36.0 + (hash(reason) % 15) / 10.0, 1),
                        heart_rate=65 + (hash(reason) % 25),
                        weight=60.0 + (hash(reason) % 30),
                        height=155.0 + (hash(reason) % 30),
                        diagnosis=_diagnosis(reason), treatment=_treatment(reason),
                        notes="Paciente colaborador. Se recomenda seguimiento.",
                    )
                    db.session.add(record)
                    db.session.flush()
                    rx = Prescription(
                        medical_record_id=record.id, patient_id=pat.id, doctor_id=doc.id, clinic_id=clinic_id,
                        medications=_medications(reason),
                        notes="Tomar con abundante agua. Suspender si presenta reaccion alergica.",
                    )
                    db.session.add(rx)
        print(f"[SEED] {past_count} citas pasadas + expedientes + recetas")

        # ============================================================
        # 8. CITAS FUTURAS
        # ============================================================
        next_wed = next_monday + timedelta(days=2)
        next_fri = next_monday + timedelta(days=4)
        future_appts = [
            (juan, doc1, next_monday, 9, 0, 30, AppointmentStatus.CONFIRMADA, "Control de seguimiento"),
            (sofia, doc1, next_monday, 9, 30, 30, AppointmentStatus.CONFIRMADA, "Revision de analisis"),
            (carlos, doc1, next_monday, 10, 0, 30, AppointmentStatus.PENDIENTE, "Dolor lumbar"),
            (lucia, doc2, next_wed, 10, 0, 30, AppointmentStatus.CONFIRMADA, "Vacunacion"),
            (pedro, doc2, next_wed, 11, 0, 30, AppointmentStatus.PENDIENTE, "Consulta general"),
            (juan, doc1, next_monday, 11, 0, 30, AppointmentStatus.CONFIRMADA, "Revision de presion arterial"),
            (sofia, doc2, next_fri, 10, 30, 30, AppointmentStatus.PENDIENTE, "Dolor de garganta"),
            (carlos, doc1, next_monday, 14, 0, 30, AppointmentStatus.CONFIRMADA, "Consulta de rutina"),
            (lucia, doc1, next_wed, 9, 0, 30, AppointmentStatus.PENDIENTE, "Dolor de espalda"),
            (pedro, doc1, next_fri, 9, 0, 30, AppointmentStatus.CONFIRMADA, "Control trimestral"),
        ]

        future_count = 0
        for pat, doc, appt_date, h, m, dur, status, reason in future_appts:
            start = datetime.combine(appt_date, time(h, m), tzinfo=UTC)
            end = start + timedelta(minutes=dur)
            if not Appointment.query.filter_by(doctor_id=doc.id, start_time=start).first():
                apt = Appointment(patient_id=pat.id, doctor_id=doc.id, receptionist_id=recep.id,
                                  clinic_id=clinic_id, start_time=start, end_time=end,
                                  status=status, reason=reason)
                db.session.add(apt)
                future_count += 1
        print(f"[SEED] {future_count} citas futuras")

        db.session.commit()

        # ============================================================
        # RESUMEN
        # ============================================================
        print("\n========================================")
        print("  SEED COMPLETADO")
        print("========================================")
        print(f"  Super-admin:    1 (super@medcenter.app)")
        print(f"  Clinicas:       {Clinic.query.count()}")
        print(f"  Suscripciones:  {Subscription.query.count()} (activa)")
        print(f"  Facturas:       {Invoice.query.count()} (pagada)")
        print(f"  Usuarios:       {User.query.count()}")
        print(f"  Medicos:        {Doctor.query.count()}")
        print(f"  Pacientes:      {Patient.query.count()}")
        print(f"  Citas:          {Appointment.query.count()}")
        print(f"  Expedientes:    {MedicalRecord.query.count()}")
        print(f"  Recetas:        {Prescription.query.count()}")
        print("========================================")


if __name__ == "__main__":
    run()
