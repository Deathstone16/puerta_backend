# Norware — Backend API

Backend de la plataforma de venta de entradas y control de acceso para boliches en Argentina.

> **Hito real:** Evento en Club Crobar el 5 de agosto de 2026 (300-1200 personas), gestionado de punta a punta con esta plataforma.

---

## Stack

| Capa | Tecnología |
|------|-----------|
| Framework | Django 6 + Django REST Framework |
| Auth | SimpleJWT (JWT propio, sin Supabase Auth) |
| Base de datos | Supabase (Postgres hosteado) — Django dueño de las migraciones |
| Pagos | Mercado Pago SDK v3 (Marketplace) |
| QR | `qrcode` + `Pillow` |
| Mail | Django SMTP configurable vía `.env` |
| Docs API | drf-spectacular (OpenAPI 3) |
| Testing | Django TestCase + factory_boy + Faker |
| Deploy | Railway o Render |

---

## Estructura del repositorio

```
puerta_backend/
├── api/
│   ├── apps/
│   │   ├── cuentas/        # Auth, usuarios y roles
│   │   ├── boliches/       # Modelo Boliche
│   │   ├── eventos/        # Modelo Evento, precio calculado, cancelación
│   │   ├── rrpp/           # RRPP, AsignacionRRPP, LinkRRPP
│   │   ├── puerta/         # Asistente, flujo guardia y cajera
│   │   └── pagos/          # Integración Mercado Pago, webhook, wallet
│   ├── config/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py
│   ├── manage.py
│   └── db.sqlite3          # Solo en desarrollo local (ignorado en git)
├── docs/
│   ├── ARCHITECTURE.md     # Decisiones de diseño y modelos de datos
│   ├── api-contract.md     # Contrato completo de endpoints
│   └── DESIGN-SYSTEM.md    # Tokens de diseño para coordinar con el frontend
├── requirements.txt
├── .env.example            # Variables de entorno requeridas (sin valores reales)
├── .gitignore
└── README.md
```

> El frontend vive en un repositorio separado.

---

## Setup de desarrollo

### 1. Clonar y crear entorno virtual

```bash
git clone https://github.com/tu-org/puerta_backend.git
cd puerta_backend

python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Configurar variables de entorno

Copiar el ejemplo y completar con los valores reales:

```bash
cp .env.example .env
```

Editar `.env` — ver sección [Variables de entorno](#variables-de-entorno) más abajo.

### 4. Migraciones y datos iniciales

```bash
cd api
python manage.py migrate
python manage.py createsuperuser
```

Cargar fixtures de usuarios de prueba (un usuario por rol):

```bash
python manage.py loaddata fixtures/usuarios_prueba.json
```

### 5. Levantar el servidor

```bash
python manage.py runserver
```

El servidor queda disponible en `http://localhost:8000`.

La documentación interactiva de la API (Swagger) queda en `http://localhost:8000/api/schema/swagger-ui/`.

---

## Variables de entorno

Todas las variables se cargan desde `.env` en la raíz del proyecto usando `python-decouple`. El archivo `.env` nunca se commitea.

```env
# Django
SECRET_KEY=cambiar-en-produccion
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=sqlite:///db.sqlite3

# En producción: cadena de conexión a Supabase
# DATABASE_URL=postgresql://usuario:password@host:5432/postgres

# CORS — URL del frontend
CORS_ALLOWED_ORIGINS=http://localhost:5173

# Mercado Pago
MP_ACCESS_TOKEN=TEST-...           # Access token de la cuenta MP de Norware
MP_COLLECTOR_ID=                   # Collector ID de la cuenta del dueño/organizador
FEE_MP_PCT=5.99                    # Porcentaje que MP cobra por transacción (estimado)
NORWARE_FEE_PCT=8.0                # Porcentaje de comisión de Norware (hardcodeado)

# Mail (SMTP)
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=SG.xxx
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=noreply@norware.com

# Frontend URL (para links en mails)
FRONTEND_URL=http://localhost:5173
```

> Para desarrollo local se puede usar SQLite (`DATABASE_URL=sqlite:///db.sqlite3`) y omitir las credenciales de Supabase. Migrar a Postgres antes del deploy.

---

## Flujo de ramas

```
main          ← solo código listo para producción, merge via PR
  └─ develop  ← rama de integración, protegida (requerir PR)
       └─ feature/nombre-corto   ← trabajo diario por dev
```

**Reglas:**
- Nunca commitear directo a `main` ni a `develop`
- Todo cambio entra por PR desde una rama `feature/`
- El `docs/api-contract.md` es la fuente de verdad — si cambia un endpoint, el PR debe incluir la actualización del contrato

---

## Correr tests

```bash
cd api
python manage.py test apps
```

Para correr tests de una sola app:

```bash
python manage.py test apps.cuentas
python manage.py test apps.puerta
```

Los tests usan la base de datos de test (se crea y destruye automáticamente). No hace falta configurar nada extra.

---

## Apps Django

| App | Responsabilidad |
|-----|----------------|
| `cuentas` | `Usuario` con roles, JWT, permisos custom |
| `boliches` | Modelo `Boliche`, relación con dueño |
| `eventos` | `Evento`, cálculo de precio, cancelación |
| `rrpp` | `RRPP`, `AsignacionRRPP`, `LinkRRPP`, generación de slugs |
| `puerta` | `Asistente`, endpoints guardia y cajera, aforo |
| `pagos` | Preferencia MP, webhook, wallet público, reembolsos |

---

## Roles del sistema

| Rol | Descripción |
|-----|-------------|
| `superadmin` | Ve métricas de todos los eventos y comisiones de Norware |
| `dueno` | Crea eventos, da de alta RRPP, audita su caja |
| `rrpp` | Genera listas, carga invitados, monitorea sus ingresos |
| `guardia` | Primer control en puerta — aprueba o rebota |
| `cajera` | Segundo control — cobra y da ingreso final |

---

## Decisiones clave

Ver `docs/ARCHITECTURE.md` para el detalle completo. Las más importantes:

- **Django dueño de las migraciones** — Supabase se usa solo como Postgres hosteado, sin Auth ni RLS
- **Sin OAuth de MP** — el dueño provee su `collector_id` manualmente; el split se hace via `application_fee` en la preferencia
- **Doble control obligatorio** — la cajera solo procesa asistentes en estado `aprobado_guardia`; si no → 409
- **Webhook MP → `aprobado_guardia`** — el pago aprobado equivale a haber pasado el primer filtro; el cliente va directo a cajera

---

## Documentación adicional

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — Modelos de datos, flujos, reglas de negocio
- [`docs/api-contract.md`](docs/api-contract.md) — Contrato completo de todos los endpoints
- [`docs/DESIGN-SYSTEM.md`](docs/DESIGN-SYSTEM.md) — Tokens de diseño para coordinar con el frontend
