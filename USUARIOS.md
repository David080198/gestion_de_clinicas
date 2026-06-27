# MedCenter Premium - Usuarios y Data de Prueba

## Plataforma activa en

> **http://localhost:8090/login**

---

## Roles disponibles

| Rol | Descripcion | Permisos |
|-----|-------------|----------|
| **Super-admin** | Gestor de la plataforma (SaaS) | Crea clinicas, asigna planes, gestiona suscripciones, ve todas las clinicas |
| **Admin** | Administrador de la clinica | Gestion de personal, reportes financieros, configuracion de la clinica |
| **Medico** | Doctor de la clinica | Su agenda, expedientes clinicos, recetas electronicas |
| **Recepcionista** | Personal de recepcion | Agendamiento de citas, cobros, registro de pacientes |
| **Paciente** | Usuario final | Ver sus citas, solicitar nuevas, descargar recetas PDF |

---

## Credenciales de acceso

### Super-admin (gestor de la plataforma)

| Campo | Valor |
|-------|-------|
| Email | `super@medcenter.app` |
| Password | `Super123!` |
| Nombre | Super Admin |

**Acceso a:** Gestiona TODAS las clinicas. Crea clinicas nuevas, asigna planes, suspende/activa clinicas, ve stats globales de billing (MRR, ingresos).

---

### Admin de clinica

| Campo | Valor |
|-------|-------|
| Email | `admin@medcenter.com` |
| Password | `Admin123!` |
| Nombre | Ana Administradora |
| Clinica | MedCenter Demo (plan Professional) |

---

### Medicos

| Campo | Dr. Gregory House | Dra. Meredith Grey |
|-------|-------------------|-------------------|
| Email | `dr.house@medcenter.com` | `dra.grey@medcenter.com` |
| Password | `Medico123!` | `Medico123!` |
| Especialidad | Medicina Interna | Pediatria |
| Tarifa | $800 MXN | $600 MXN |
| Horario | Lun-Vie 09:00-18:00 | Lun-Mie-Vie 10:00-14:00 |

---

### Recepcionista

| Campo | Valor |
|-------|-------|
| Email | `recep@medcenter.com` |
| Password | `Recep123!` |
| Nombre | Maria Gonzalez |

---

### Pacientes

| Nombre | Email | Password | Documento |
|--------|-------|----------|-----------|
| Juan Perez | `juan@paciente.com` | `Secret123` | DOC123 |
| Lucia Martinez | `lucia@paciente.com` | `Secret123` | DOC456 |
| Carlos Ramirez | `carlos@paciente.com` | `Secret123` | DOC789 |
| Sofia Lopez | `sofia@paciente.com` | `Secret123` | DOC012 |
| Pedro Ruiz | `pedro@paciente.com` | `Secret123` | DOC345 |

---

## Resumen rapido

| Rol | Email | Password |
|-----|-------|----------|
| Super-admin | super@medcenter.app | `Super123!` |
| Admin | admin@medcenter.com | `Admin123!` |
| Medico | dr.house@medcenter.com | `Medico123!` |
| Medico | dra.grey@medcenter.com | `Medico123!` |
| Recepcionista | recep@medcenter.com | `Recep123!` |
| Paciente | juan@paciente.com | `Secret123` |
| Paciente | lucia@paciente.com | `Secret123` |
| Paciente | carlos@paciente.com | `Secret123` |
| Paciente | sofia@paciente.com | `Secret123` |
| Paciente | pedro@paciente.com | `Secret123` |

---

## Data cargada en la plataforma

| Recurso | Cantidad |
|---------|----------|
| Clinicas | 1 (MedCenter Demo, plan Professional) |
| Suscripciones | 1 (activa, $3,500/mes) |
| Facturas | 1 (pagada) |
| Usuarios | 10 |
| Medicos | 2 |
| Pacientes | 5 |
| Citas | 18 (8 completadas + 6 confirmadas + 4 pendientes) |
| Expedientes clinicos | 8 (inmutables) |
| Recetas electronicas | 8 (descargables en PDF) |

---

## Suscripcion de la clinica demo

| Campo | Valor |
|-------|-------|
| Plan | Professional |
| Ciclo | Mensual |
| Precio | $3,500 MXN/mes |
| Estado | Activa |
| Auto-renovacion | Si |
| Factura | Pagada ($3,500) |

---

## Como probar la plataforma

1. **Super-admin:** entra con `super@medcenter.app` para ver stats de billing y gestionar clinicas.
2. **Admin:** entra con `admin@medcenter.com` para ver ingresos, top medicos y graficas.
3. **Medico:** entra con `dr.house@medcenter.com` para ver citas del dia y crear expedientes.
4. **Recepcionista:** entra con `recep@medcenter.com` para ver sala de espera y agendar citas.
5. **Paciente:** entra con `juan@paciente.com` para ver proximas citas, historial y recetas PDF.
