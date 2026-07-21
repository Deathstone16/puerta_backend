# Norware — Arquitectura del Backend

## Índice

1. [Decisiones de arquitectura](#1-decisiones-de-arquitectura)
2. [Modelos de datos](#2-modelos-de-datos)
3. [Flujo de pagos](#3-flujo-de-pagos)
4. [Flujo de puerta](#4-flujo-de-puerta)
5. [Roles y permisos](#5-roles-y-permisos)
6. [Estados del Asistente](#6-estados-del-asistente)
7. [Cancelación de evento](#7-cancelación-de-evento)
8. [Estructura de apps Django](#8-estructura-de-apps-django)
9. [Configuración de settings](#9-configuración-de-settings)

---

## 1. Decisiones de arquitectura

### Django hace todo el trabajo pesado
Django es dueño de la lógica de negocio, el ORM, las migraciones, la autenticación JWT y los endpoints REST. No se delega nada a Supabase más allá del almacenamiento.

### Supabase = Postgres hosteado
Supabase se usa únicamente como base de datos Postgres en la nube. **No se usa** Supabase Auth, Supabase RLS, ni el cliente JS de Supabase. Django corre todas las migraciones con `manage.py migrate`.

### JWT propio con SimpleJWT
Autenticación stateless via JWT. Los tokens incluyen el campo `rol` del usuario en el payload. No hay sesiones de Django en ninguna ruta de la API.

### Sin OAuth de Mercado Pago (decisión de MVP)
El dueño provee su `collector_id` de MP manualmente al configurar su perfil. El split de pagos se hace via `application_fee` en la preferencia de MP. OAuth multi-vendedor se evalúa post-MVP cuando haya más de un boliche en la plataforma.

### Polling para aforo en vivo
El frontend consulta `GET /api/dashboard/aforo/:evento_id/` cada 3-5 segundos. Si el volumen de eventos crece, se puede sumar Supabase Realtime como capa extra sin tocar el backend.

### SQLite en desarrollo, Postgres en producción
Arrancar con SQLite elimina fricción para nuevos devs. La variable `DATABASE_URL` en `.env` controla cuál se usa. Migrar a Supabase Postgres antes de cualquier deploy.

---

## 2. Modelos de datos

### App `cuentas`

```python
class Usuario(AbstractUser):
    ROLES = [
        ('superadmin', 'Super Admin'),
        ('dueno',      'Dueño'),
        ('rrpp',       'RRPP'),
        ('guardia',    'Guardia'),
        ('cajera',     'Cajera'),
    ]
    rol      = CharField(max_length=20, choices=ROLES)
    telefono = CharField(max_length=20, blank=True, null=True)
```

`AUTH_USER_MODEL = 'cuentas.Usuario'` — registrado antes de la primera migración.

---

### App `boliches`

```python
class Boliche(Model):
    nombre          = CharField(max_length=200)
    direccion       = TextField()
    dueno           = ForeignKey(Usuario, on_delete=PROTECT, related_name='boliches')
    collector_id_mp = CharField(max_length=100)  # ID de cuenta MP del organizador
    created_at      = DateTimeField(auto_now_add=True)
```

`collector_id_mp` es el ID público de la cuenta de Mercado Pago del dueño. Se usa en la creación de la preferencia de pago para que el dinero llegue a su cuenta.

---

### App `eventos`

```python
class Evento(Model):
    ESTADOS = [('activo', 'Activo'), ('cancelado', 'Cancelado')]

    boliche            = ForeignKey(Boliche, on_delete=PROTECT)
    nombre             = CharField(max_length=200)
    fecha              = DateTimeField()
    aforo_max          = PositiveIntegerField()
    color_pulsera      = CharField(max_length=50)   # ej: "violeta", "#8B5CF6"
    precio_base        = DecimalField(max_digits=10, decimal_places=2)
    line_up            = JSONField(default=list)    # [{"artista": "...", "horario": "..."}]
    estado             = CharField(max_length=20, choices=ESTADOS, default='activo')
    motivo_cancelacion = TextField(blank=True, null=True)
    created_at         = DateTimeField(auto_now_add=True)
    updated_at         = DateTimeField(auto_now=True)

    @property
    def precio_publicado(self):
        from .utils import calcular_precio_publicado
        return calcular_precio_publicado(self.precio_base)['precio_publicado']
```

**Función `calcular_precio_publicado(precio_base)`** en `eventos/utils.py`:

```python
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings

def calcular_precio_publicado(precio_base):
    base      = Decimal(str(precio_base))
    fee_mp    = (base * Decimal(str(settings.FEE_MP_PCT)) / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    fee_nw    = (base * Decimal(str(settings.NORWARE_FEE_PCT)) / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    publicado = (base + fee_mp + fee_nw).quantize(Decimal('1'), rounding=ROUND_HALF_UP)  # redondeo a entero
    return {
        'precio_base':      int(base),
        'fee_mp':           float(fee_mp),
        'fee_norware':      float(fee_nw),
        'precio_publicado': int(publicado),
    }
```

> `FEE_MP_PCT` y `NORWARE_FEE_PCT` se leen de `.env` y se exponen en `settings.py`. El dueño no los edita.

---

### App `rrpp`

```python
class RRPP(Model):
    TIPO_COMISION = [('fijo', 'Monto fijo'), ('porcentaje', 'Porcentaje')]

    usuario        = OneToOneField(Usuario, on_delete=CASCADE, related_name='perfil_rrpp')
    boliche        = ForeignKey(Boliche, on_delete=PROTECT)
    tipo_comision  = CharField(max_length=20, choices=TIPO_COMISION)
    valor_comision = DecimalField(max_digits=10, decimal_places=2)
    # fijo: monto en ARS por cada asistente ingresado
    # porcentaje: % del monto recaudado atribuido a ese RRPP


class AsignacionRRPP(Model):
    rrpp    = ForeignKey(RRPP, on_delete=CASCADE, related_name='asignaciones')
    evento  = ForeignKey(Evento, on_delete=CASCADE, related_name='asignaciones_rrpp')
    activa  = BooleanField(default=True)

    class Meta:
        unique_together = ('rrpp', 'evento')

    # Al hacer save() por primera vez, genera 2 instancias de LinkRRPP automáticamente
    # (via signal post_save o override de save())


class LinkRRPP(Model):
    TIPOS = [('lista', 'Lista'), ('venta_web', 'Venta Web')]

    asignacion = ForeignKey(AsignacionRRPP, on_delete=CASCADE, related_name='links')
    tipo       = CharField(max_length=20, choices=TIPOS)
    slug       = UUIDField(default=uuid4, unique=True, editable=False)
    activo     = BooleanField(default=True)

    # URL pública: /lista/{slug}/ (lista) o /venta/{slug}/ (venta_web)
```

---

### App `puerta`

```python
class Asistente(Model):
    TIPO_INGRESO = [
        ('web_anticipada', 'Compra Web'),
        ('lista_rrpp',     'Lista RRPP'),
        ('venta_general',  'Venta General en Puerta'),
    ]
    ESTADOS = [
        ('pendiente',          'Pendiente'),
        ('aprobado_guardia',   'Aprobado por Guardia'),
        ('rebotado_guardia',   'Rebotado por Guardia'),
        ('ingresado_final',    'Ingresado'),
    ]
    METODOS_PAGO = [
        ('efectivo',      'Efectivo'),
        ('transferencia', 'Transferencia'),
        ('ya_pago_web',   'Ya pagó por web'),
    ]

    evento       = ForeignKey(Evento, on_delete=PROTECT, related_name='asistentes')
    link_rrpp    = ForeignKey(LinkRRPP, on_delete=SET_NULL, null=True, blank=True)
    nombre       = CharField(max_length=100)
    apellido     = CharField(max_length=100)
    dni          = CharField(max_length=20)
    tipo_ingreso = CharField(max_length=30, choices=TIPO_INGRESO)
    estado       = CharField(max_length=30, choices=ESTADOS, default='pendiente')

    metodo_pago  = CharField(max_length=20, choices=METODOS_PAGO, null=True, blank=True)
    monto_pagado = DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    wallet_token    = UUIDField(default=uuid4, unique=True, editable=False)
    mp_payment_id   = CharField(max_length=100, null=True, blank=True, unique=True)
    mp_fee_norware  = DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    # Guarda el application_fee real cobrado por Norware en esa transacción

    motivo_rechazo = TextField(blank=True, null=True)

    created_at    = DateTimeField(auto_now_add=True)
    aprobado_at   = DateTimeField(null=True, blank=True)
    ingresado_at  = DateTimeField(null=True, blank=True)
    rebotado_at   = DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('evento', 'dni')  # Un DNI por evento
```

---

## 3. Flujo de pagos

```
Cliente                  Frontend              Django Backend         Mercado Pago
   |                        |                        |                      |
   |--- Elige entrada ------>|                        |                      |
   |                        |-- POST /api/pagos/     |                      |
   |                        |   preferencia/ ------->|                      |
   |                        |                        |-- Crea preferencia -->|
   |                        |                        |   application_fee     |
   |                        |                        |   collector_id        |
   |                        |                        |<-- init_point --------|
   |                        |<-- {init_point} --------|                      |
   |<-- Redirige a MP -------|                        |                      |
   |                        |                        |                      |
   |--- Paga en MP --------------------------------------------------------->|
   |                        |                        |                      |
   |                        |                        |<-- Webhook pago ------|
   |                        |                        |    aprobado           |
   |                        |                        |                      |
   |                        |             Crea Asistente                    |
   |                        |             tipo: web_anticipada              |
   |                        |             estado: aprobado_guardia          |
   |                        |             guarda mp_payment_id              |
   |                        |             guarda mp_fee_norware             |
   |                        |                        |                      |
   |                        |             Envía mail con                    |
   |                        |             /wallet/:token                    |
   |<-- Mail con link QR ----|                        |                      |
```

**Desglose del pago:**
```
precio_publicado = precio_base + fee_mp + fee_norware
                    ↓               ↓          ↓
               → dueño (neto   → MP retiene  → Norware retiene
                 después de MP)  su comisión   via application_fee
```

**Idempotencia del webhook:** antes de crear el `Asistente`, Django verifica si ya existe uno con ese `mp_payment_id`. Si existe, devuelve 200 sin crear duplicado.

---

## 4. Flujo de puerta

```
Cliente llega a la puerta
         │
         ▼
┌─────────────────┐
│     GUARDIA     │  mobile-first, una mano, poca luz
│                 │
│  Escanea QR     │
│  o busca DNI    │
└────────┬────────┘
         │
    ┌────┴─────┐
    │          │
    ▼          ▼
REBOTAR    APROBAR
    │          │
    │     estado → aprobado_guardia
    │          │
    ▼          ▼
[TERMINAL]  ┌──────────────────────────────┐
            │          CAJERA              │
            │  mobile/tablet               │
            │                              │
            │  A) Web anticipada:          │
            │     2do escaneo QR           │
            │     → ingresado_final        │
            │     método: ya_pago_web      │
            │                              │
            │  B) Lista RRPP:              │
            │     busca DNI                │
            │     cobra Efectivo/Transfer  │
            │     → ingresado_final        │
            │                              │
            │  C) Venta general:           │
            │     carga DNI + nombre       │
            │     cobra                    │
            │     → ingresado_final        │
            └──────────────────────────────┘
                         │
                         ▼
               aforo +1, impacta métricas
               del dueño y del RRPP
```

**Reglas críticas:**
- La cajera **solo** puede procesar asistentes en `aprobado_guardia` → si no, 409
- `rebotado_guardia` es un estado terminal — no puede pasar a cajera ni ser revertido
- `deshacer` disponible en cajera dentro de los 10 minutos de `ingresado_at`
- Todos los endpoints de guardia y cajera verifican `evento.estado == 'activo'` → si `cancelado`, 423

---

## 5. Roles y permisos

Los permisos custom viven en `apps/cuentas/permissions.py`:

```python
class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol == 'superadmin'

class IsDueno(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol == 'dueno'

class IsRRPP(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol == 'rrpp'

class IsGuardia(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol == 'guardia'

class IsCajera(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol == 'cajera'
```

| Endpoint | Permisos |
|----------|---------|
| `GET /api/eventos/` | Público |
| `GET /api/eventos/:id/` | Público |
| `POST /api/eventos/` | IsDueno |
| `PATCH /api/eventos/:id/` | IsDueno |
| `POST /api/eventos/:id/cancelar/` | IsDueno |
| `GET /api/lista/:slug/` | Público |
| `POST /api/lista/:slug/anotar/` | Público |
| `GET /api/rrpp/mi-panel/` | IsRRPP |
| `POST /api/rrpp/anotar-invitado/` | IsRRPP |
| `POST /api/puerta/guardia/*` | IsGuardia |
| `POST /api/puerta/cajera/*` | IsCajera |
| `GET /api/dashboard/aforo/:id/` | IsDueno, IsCajera, IsGuardia |
| `GET /api/dashboard/recaudacion/:id/` | IsDueno |
| `GET /api/dashboard/ranking-rrpp/:id/` | IsDueno |
| `GET /api/admin/metricas/` | IsSuperAdmin |
| `GET /api/wallet/:token/` | Público |
| `POST /api/pagos/webhook/` | Público (validar firma MP) |

---

## 6. Estados del Asistente

```
                    ┌──────────┐
    (anotado en     │ PENDIENTE│ ← creado via lista RRPP (pública o manual)
     lista RRPP)    └────┬─────┘
                         │ guardia escanea / busca
              ┌──────────┴──────────┐
              │                     │
              ▼                     ▼
   ┌──────────────────┐   ┌──────────────────┐
   │ APROBADO_GUARDIA │   │ REBOTADO_GUARDIA │ ← TERMINAL (dress code,
   └────────┬─────────┘   └──────────────────┘   estado, etc.)
            │ cajera procesa
            ▼
   ┌──────────────────┐
   │ INGRESADO_FINAL  │ ← aforo +1
   └──────────────────┘
        (reversible dentro de 10 min via deshacer → vuelve a APROBADO_GUARDIA)


Compra web (webhook MP):
   ┌──────────────────┐
   │ APROBADO_GUARDIA │ ← creado directamente aquí (pago = validación)
   └────────┬─────────┘
            │ cajera escanea 2do QR
            ▼
   ┌──────────────────┐
   │ INGRESADO_FINAL  │
   └──────────────────┘

Venta general en puerta:
   ┌──────────────────┐
   │ INGRESADO_FINAL  │ ← creado directamente aquí
   └──────────────────┘
```

---

## 7. Cancelación de evento

Cuando el dueño cancela un evento (`POST /api/eventos/:id/cancelar/`):

1. `estado` cambia a `cancelado`, se guarda `motivo_cancelacion`
2. Se dispara `reembolsar_evento(evento_id)` — itera todos los `Asistente` con `tipo_ingreso='web_anticipada'` y llama a la API de reembolso de MP con idempotency key `refund-{asistente.id}`
3. Todos los endpoints de guardia y cajera para ese evento devuelven **423** con mensaje "SISTEMA BLOQUEADO - EVENTO CANCELADO"
4. Los links de RRPP (`LinkRRPP.activo`) quedan inactivos

**El evento nunca se elimina si tiene asistentes.** `DELETE` sobre un evento con asistentes devuelve 405.

---

## 8. Estructura de apps Django

```
api/
├── apps/
│   ├── cuentas/
│   │   ├── models.py       # Usuario(AbstractUser) con campo rol
│   │   ├── permissions.py  # IsSuperAdmin, IsDueno, IsRRPP, IsGuardia, IsCajera
│   │   ├── serializers.py  # UserSerializer, TokenSerializer custom
│   │   ├── views.py        # LoginView (TokenObtainPairView custom)
│   │   ├── urls.py
│   │   └── tests.py
│   ├── boliches/
│   │   ├── models.py       # Boliche
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── tests.py
│   ├── eventos/
│   │   ├── models.py       # Evento
│   │   ├── utils.py        # calcular_precio_publicado()
│   │   ├── serializers.py  # incluye precio_publicado como campo calculado
│   │   ├── views.py        # EventoViewSet, CancelarEventoView, CalcularPrecioView
│   │   ├── urls.py
│   │   └── tests.py
│   ├── rrpp/
│   │   ├── models.py       # RRPP, AsignacionRRPP, LinkRRPP
│   │   ├── signals.py      # post_save AsignacionRRPP → genera 2 LinkRRPP
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── tests.py
│   ├── puerta/
│   │   ├── models.py       # Asistente
│   │   ├── mixins.py       # EventoActivoMixin (verifica cancelación)
│   │   ├── serializers.py
│   │   ├── views.py        # GuardiaView, CajeraView, AforoView
│   │   ├── urls.py
│   │   └── tests.py
│   └── pagos/
│       ├── models.py       # (sin modelos propios; usa Asistente de puerta)
│       ├── mp_client.py    # Wrapper del SDK de Mercado Pago
│       ├── views.py        # PreferenciaView, WebhookView, WalletView
│       ├── urls.py
│       └── tests.py
└── config/
    ├── settings.py
    ├── urls.py             # incluye todas las urls de las apps bajo /api/
    ├── wsgi.py
    └── asgi.py
```

---

## 9. Configuración de settings

Variables que deben existir en `settings.py` además del setup estándar de Django:

```python
# DRF
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# JWT
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(hours=8),   # duración larga para noches de evento
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
}

# CORS
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='http://localhost:5173').split(',')

# Mercado Pago
MP_ACCESS_TOKEN   = config('MP_ACCESS_TOKEN')
MP_COLLECTOR_ID   = config('MP_COLLECTOR_ID')
FEE_MP_PCT        = config('FEE_MP_PCT', default=5.99, cast=float)
NORWARE_FEE_PCT   = config('NORWARE_FEE_PCT', default=8.0, cast=float)

# Mail
EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST          = config('EMAIL_HOST')
EMAIL_PORT          = config('EMAIL_PORT', default=587, cast=int)
EMAIL_HOST_USER     = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
EMAIL_USE_TLS       = config('EMAIL_USE_TLS', default=True, cast=bool)
DEFAULT_FROM_EMAIL  = config('DEFAULT_FROM_EMAIL', default='noreply@norware.com')

# URL base del frontend (para links en mails)
FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:5173')

# drf-spectacular
SPECTACULAR_SETTINGS = {
    'TITLE': 'Norware API',
    'DESCRIPTION': 'Backend de la plataforma de venta y control de acceso para boliches',
    'VERSION': '1.0.0',
}
```
