# Documento de Diseño — App `puerta`

## Resumen ejecutivo

La app `puerta` implementa el flujo operativo de la noche: guardia escanea → aprueba/rebota → cajera cobra → ingreso final. El modelo `Asistente` es el core de toda la plataforma — lo crean `rrpp` (lista), `pagos` (web) y `puerta` misma (venta general). Las reglas más críticas son el doble control obligatorio y el estado terminal de `rebotado_guardia`.

**Decisiones de diseño principales:**
- `EventoActivoMixin` como mixin reutilizable — todas las vistas de guardia y cajera lo heredan
- Venta general crea asistentes directamente en `ingresado_final` (el guardia ya los dejó pasar físicamente en la fila)
- `deshacer` solo disponible 10 minutos — ventana corta para errores, no para abuso
- Búsqueda por `wallet_token` (QR) o `(dni, evento_id)` en un único endpoint de escaneo
- `aforo` como endpoint simple de conteo — el frontend hace polling cada 3-5s

---

## Arquitectura

```
┌───────────────────────────────────────────────────────┐
│  Público (sin auth)                                    │
│  GET  /api/lista/:slug/                               │
│  POST /api/lista/:slug/anotar/                        │
└─────────────────────┬─────────────────────────────────┘
                      │
┌─────────────────────▼─────────────────────────────────┐
│  Guardia (IsGuardia + EventoActivoMixin)               │
│  POST /api/puerta/guardia/escanear/                   │
│  POST /api/puerta/guardia/aprobar/:id/                │
│  POST /api/puerta/guardia/rebotar/:id/                │
└─────────────────────┬─────────────────────────────────┘
                      │ solo asistentes aprobado_guardia
┌─────────────────────▼─────────────────────────────────┐
│  Cajera (IsCajera + EventoActivoMixin)                 │
│  POST /api/puerta/cajera/escanear-web/:id/            │
│  POST /api/puerta/cajera/cobrar-lista/:id/            │
│  POST /api/puerta/cajera/venta-general/               │
│  POST /api/puerta/cajera/deshacer/:id/                │
└─────────────────────┬─────────────────────────────────┘
                      │ ingresado_final → aforo +1
┌─────────────────────▼─────────────────────────────────┐
│  Dashboard (IsDueno | IsCajera | IsGuardia)            │
│  GET /api/dashboard/aforo/:evento_id/                 │
└───────────────────────────────────────────────────────┘
```

---

## Componentes e interfaces

### Modelo `Asistente`

```python
# apps/puerta/models.py
import uuid
from django.db import models


class Asistente(models.Model):
    TIPO_INGRESO = [
        ('web_anticipada', 'Compra Web'),
        ('lista_rrpp',     'Lista RRPP'),
        ('venta_general',  'Venta General'),
    ]
    ESTADOS = [
        ('pendiente',        'Pendiente'),
        ('aprobado_guardia', 'Aprobado por Guardia'),
        ('rebotado_guardia', 'Rebotado por Guardia'),
        ('ingresado_final',  'Ingresado'),
    ]
    METODOS_PAGO = [
        ('efectivo',      'Efectivo'),
        ('transferencia', 'Transferencia'),
        ('ya_pago_web',   'Ya pagó por web'),
    ]

    evento       = models.ForeignKey('eventos.Evento',   on_delete=models.PROTECT, related_name='asistentes')
    link_rrpp    = models.ForeignKey('rrpp.LinkRRPP',    on_delete=models.SET_NULL, null=True, blank=True, related_name='asistentes')
    nombre       = models.CharField(max_length=100)
    apellido     = models.CharField(max_length=100)
    dni          = models.CharField(max_length=20)
    tipo_ingreso = models.CharField(max_length=20, choices=TIPO_INGRESO)
    estado       = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    metodo_pago  = models.CharField(max_length=20, choices=METODOS_PAGO, null=True, blank=True)
    monto_pagado = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    wallet_token   = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    mp_payment_id  = models.CharField(max_length=100, null=True, blank=True, unique=True)
    mp_fee_norware = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    motivo_rechazo = models.TextField(blank=True, null=True)

    created_at   = models.DateTimeField(auto_now_add=True)
    aprobado_at  = models.DateTimeField(null=True, blank=True)
    ingresado_at = models.DateTimeField(null=True, blank=True)
    rebotado_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = 'Asistente'
        verbose_name_plural = 'Asistentes'
        unique_together     = ('evento', 'dni')

    def __str__(self):
        return f"{self.nombre} {self.apellido} — DNI {self.dni} ({self.estado})"
```

---

### Mixin `EventoActivoMixin`

```python
# apps/puerta/mixins.py
from rest_framework.response import Response
from rest_framework import status


class EventoActivoMixin:
    """
    Mixin que verifica que el evento asociado a la operación esté activo.
    Si el evento está cancelado, devuelve HTTP 423.

    Uso: las vistas heredan este mixin y llaman a self.verificar_evento_activo(evento).
    """

    def verificar_evento_activo(self, evento):
        if evento.estado == 'cancelado':
            return Response(
                {
                    'error':  'SISTEMA BLOQUEADO - EVENTO CANCELADO',
                    'motivo': evento.motivo_cancelacion or '',
                },
                status=status.HTTP_423_LOCKED
            )
        return None  # evento activo, continuar
```

**Uso en vistas:**
```python
class GuardiaAprobarView(EventoActivoMixin, APIView):
    def post(self, request, pk):
        asistente = get_object_or_404(Asistente, pk=pk)
        bloqueo = self.verificar_evento_activo(asistente.evento)
        if bloqueo:
            return bloqueo
        # ... resto de la lógica
```

---

### Vistas de lista pública

```python
# Endpoint: GET /api/lista/:slug/
class ListaInfoView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        link = get_object_or_404(LinkRRPP, slug=slug, tipo='lista')
        if not link.activo:
            return Response({'error': 'Este link está inactivo'}, status=410)
        anotados = Asistente.objects.filter(link_rrpp=link).count()
        return Response({
            'evento': {...},         # nombre, fecha, boliche, color_pulsera
            'rrpp_nombre': ...,
            'link_activo': True,
            'anotados': anotados,
        })

# Endpoint: POST /api/lista/:slug/anotar/
class ListaAnotarView(EventoActivoMixin, APIView):
    permission_classes = [AllowAny]

    def post(self, request, slug):
        link = get_object_or_404(LinkRRPP, slug=slug, tipo='lista')
        if not link.activo:
            return Response({'error': 'Este link está inactivo'}, status=410)
        bloqueo = self.verificar_evento_activo(link.asignacion.evento)
        if bloqueo:
            return bloqueo
        # Validar nombre, apellido, dni
        # Verificar unicidad DNI en el evento → 409 si existe
        # Crear Asistente
```

---

### Vistas de guardia

```python
# POST /api/puerta/guardia/escanear/
class GuardiaEscanearView(EventoActivoMixin, APIView):
    permission_classes = [IsGuardia]

    def post(self, request):
        # Busca por qr_code (wallet_token) o por (dni + evento_id)
        if 'qr_code' in request.data:
            asistente = get_object_or_404(Asistente, wallet_token=request.data['qr_code'])
        else:
            dni       = request.data.get('dni')
            evento_id = request.data.get('evento_id')
            asistente = get_object_or_404(Asistente, dni=dni, evento_id=evento_id)

        bloqueo = self.verificar_evento_activo(asistente.evento)
        if bloqueo:
            return bloqueo

        return Response(AsistenteBriefSerializer(asistente).data)

# POST /api/puerta/guardia/aprobar/:id/
class GuardiaAprobarView(EventoActivoMixin, APIView):
    permission_classes = [IsGuardia]

    def post(self, request, pk):
        asistente = get_object_or_404(Asistente, pk=pk)
        bloqueo = self.verificar_evento_activo(asistente.evento)
        if bloqueo:
            return bloqueo
        if asistente.estado != 'pendiente':
            return Response({'error': 'El asistente no está en estado pendiente'}, status=400)
        asistente.estado     = 'aprobado_guardia'
        asistente.aprobado_at = now()
        asistente.save(update_fields=['estado', 'aprobado_at'])
        return Response({'id': asistente.id, 'estado': 'aprobado_guardia',
                         'aprobado_at': asistente.aprobado_at,
                         'mensaje': 'Aprobado. Pasa a caja.'})

# POST /api/puerta/guardia/rebotar/:id/
class GuardiaRebotarView(EventoActivoMixin, APIView):
    permission_classes = [IsGuardia]

    def post(self, request, pk):
        asistente = get_object_or_404(Asistente, pk=pk)
        bloqueo = self.verificar_evento_activo(asistente.evento)
        if bloqueo:
            return bloqueo
        if asistente.estado != 'pendiente':
            return Response({'error': 'El asistente no está en estado pendiente'}, status=400)
        motivo = request.data.get('motivo', '').strip()
        if not motivo:
            return Response({'error': 'El motivo es obligatorio'}, status=400)
        asistente.estado         = 'rebotado_guardia'
        asistente.rebotado_at    = now()
        asistente.motivo_rechazo = motivo
        asistente.save(update_fields=['estado', 'rebotado_at', 'motivo_rechazo'])
        return Response({'id': asistente.id, 'estado': 'rebotado_guardia',
                         'rebotado_at': asistente.rebotado_at, 'motivo': motivo})
```

---

### Vistas de cajera

```python
# Validación común para cajera
def _validar_aprobado_guardia(asistente):
    if asistente.estado != 'aprobado_guardia':
        return Response({
            'error': 'Falta validación del guardia',
            'estado_actual': asistente.estado,
        }, status=409)
    return None

# POST /api/puerta/cajera/escanear-web/:id/
# Valida tipo_ingreso == 'web_anticipada' y estado == 'aprobado_guardia'
# → ingresado_final, metodo_pago='ya_pago_web', ingresado_at=now()

# POST /api/puerta/cajera/cobrar-lista/:id/
# Valida tipo_ingreso == 'lista_rrpp' y estado == 'aprobado_guardia'
# → ingresado_final, metodo_pago, monto_pagado, ingresado_at=now()

# POST /api/puerta/cajera/venta-general/
# Crea N asistentes directamente en ingresado_final
# Verifica unicidad de DNIs antes de crear (bulk check → 409 con DNIs conflictivos)
# Usa bulk_create para eficiencia

# POST /api/puerta/cajera/deshacer/:id/
# Verifica estado == 'ingresado_final'
# Verifica ingresado_at > now() - 10 minutos → si no, 403
# Revierte: estado='aprobado_guardia', ingresado_at=None, metodo_pago=None, monto_pagado=None
```

---

### Vista de aforo

```python
# GET /api/dashboard/aforo/:evento_id/
class AforoView(APIView):
    permission_classes = [IsGuardia | IsCajera | IsDueno]

    def get(self, request, evento_id):
        evento     = get_object_or_404(Evento, pk=evento_id)
        ingresados = Asistente.objects.filter(evento=evento, estado='ingresado_final').count()
        pendientes = Asistente.objects.filter(evento=evento, estado__in=['pendiente', 'aprobado_guardia']).count()
        porcentaje = round((ingresados / evento.aforo_max) * 100, 2) if evento.aforo_max else 0
        return Response({
            'evento_id':  evento_id,
            'ingresados': ingresados,
            'aforo_max':  evento.aforo_max,
            'porcentaje': porcentaje,
            'pendientes': pendientes,
        })
```

**Nota sobre `IsGuardia | IsCajera | IsDueno`:** DRF permite composición de permisos con el operador `|` desde la versión 3.9. Si la versión instalada no lo soporta, usar un permiso custom `IsStaff` que verifique `rol in ['guardia', 'cajera', 'dueno']`.

---

### URLs

```python
# apps/puerta/urls.py
from django.urls import path
from .views import (
    ListaInfoView, ListaAnotarView,
    GuardiaEscanearView, GuardiaAprobarView, GuardiaRebotarView,
    CajeraEscanearWebView, CajeraCobrarListaView,
    CajeraVentaGeneralView, CajeraDeshacerView,
    AforoView,
)

lista_urlpatterns = [
    path('<uuid:slug>/',        ListaInfoView.as_view(),   name='lista-info'),
    path('<uuid:slug>/anotar/', ListaAnotarView.as_view(), name='lista-anotar'),
]

guardia_urlpatterns = [
    path('escanear/',        GuardiaEscanearView.as_view(), name='guardia-escanear'),
    path('aprobar/<int:pk>/', GuardiaAprobarView.as_view(),  name='guardia-aprobar'),
    path('rebotar/<int:pk>/', GuardiaRebotarView.as_view(),  name='guardia-rebotar'),
]

cajera_urlpatterns = [
    path('escanear-web/<int:pk>/', CajeraEscanearWebView.as_view(),  name='cajera-escanear-web'),
    path('cobrar-lista/<int:pk>/', CajeraCobrarListaView.as_view(),   name='cajera-cobrar-lista'),
    path('venta-general/',         CajeraVentaGeneralView.as_view(),  name='cajera-venta-general'),
    path('deshacer/<int:pk>/',     CajeraDeshacerView.as_view(),      name='cajera-deshacer'),
]

dashboard_urlpatterns = [
    path('aforo/<int:evento_id>/', AforoView.as_view(), name='aforo'),
]

# En config/urls.py:
# path('api/lista/',          include(lista_urlpatterns)),
# path('api/puerta/guardia/', include(guardia_urlpatterns)),
# path('api/puerta/cajera/',  include(cajera_urlpatterns)),
# path('api/dashboard/',      include(dashboard_urlpatterns)),
```

---

### Admin

```python
# apps/puerta/admin.py
@admin.register(Asistente)
class AsistenteAdmin(ModelAdmin):
    list_display   = ['nombre', 'apellido', 'dni', 'evento', 'tipo_ingreso', 'estado', 'metodo_pago', 'created_at']
    list_filter    = ['estado', 'tipo_ingreso', 'metodo_pago', 'evento']
    search_fields  = ['nombre', 'apellido', 'dni']
    readonly_fields = ['wallet_token', 'mp_payment_id', 'created_at', 'aprobado_at', 'ingresado_at', 'rebotado_at']
```

---

## Modelo de datos — `Asistente`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `evento` | FK(Evento) PROTECT | Evento al que asiste |
| `link_rrpp` | FK(LinkRRPP) nullable | Link de RRPP de origen (null si web o general) |
| `nombre` / `apellido` | CharField(100) | Identificación |
| `dni` | CharField(20) | Documento — único por evento |
| `tipo_ingreso` | CharField choices | `web_anticipada` / `lista_rrpp` / `venta_general` |
| `estado` | CharField choices | `pendiente` → `aprobado_guardia` / `rebotado_guardia` → `ingresado_final` |
| `metodo_pago` | CharField nullable | `efectivo` / `transferencia` / `ya_pago_web` |
| `monto_pagado` | Decimal nullable | Monto cobrado en puerta (null para web) |
| `wallet_token` | UUID unique | Token público del ticket QR |
| `mp_payment_id` | CharField nullable unique | ID de pago en MP (solo web) |
| `mp_fee_norware` | Decimal nullable | Fee cobrado por Norware en esa transacción |
| `motivo_rechazo` | TextField nullable | Solo si rebotado |
| `*_at` | DateTimeField nullable | Timestamps de cada transición de estado |

---

## Propiedades de correctitud

### Propiedad 1: Doble control obligatorio

Para cualquier Asistente con `estado != 'aprobado_guardia'`, cualquier endpoint de cajera (salvo `venta-general`) SHALL devolver HTTP 409.

**Valida: Requisito 6.4**

### Propiedad 2: Rebotado es estado terminal

Para cualquier Asistente con `estado = 'rebotado_guardia'`, ninguna operación puede cambiar su estado a `aprobado_guardia` o `ingresado_final`.

**Valida: Requisito 5.4**

### Propiedad 3: Deshacer tiene ventana temporal

Para cualquier Asistente con `estado = 'ingresado_final'`, `deshacer` SHALL fallar con 403 si `now() - ingresado_at > 10 minutos`.

**Valida: Requisito 7.2**

---

## Manejo de errores

| Escenario | Código | Mensaje |
|-----------|--------|---------|
| Evento cancelado | 423 | "SISTEMA BLOQUEADO - EVENTO CANCELADO" |
| Cajera: asistente no aprobado por guardia | 409 | "Falta validación del guardia" |
| Guardia: asistente no en pendiente | 400 | "El asistente no está en estado pendiente" |
| Rebotar sin motivo | 400 | "El motivo es obligatorio" |
| Deshacer fuera de ventana | 403 | "No se puede deshacer: pasaron más de 10 minutos" |
| DNI duplicado en evento | 409 | "Este DNI ya está registrado en el evento" |
| Link inactivo | 410 | "Este link está inactivo" |
| Asistente/evento no encontrado | 404 | — |

---

## Estrategia de testing

1. `test_flujo_completo_lista_guardia_cajera` — flujo end-to-end: anotar → aprobar → cobrar → aforo +1
2. `test_cajera_rechaza_pendiente` — 409 doble control
3. `test_cajera_rechaza_rebotado` — 409 estado terminal
4. `test_rebotado_es_terminal` — no puede avanzar
5. `test_deshacer_dentro_de_ventana` — OK
6. `test_deshacer_fuera_de_ventana` — 403
7. `test_venta_general_crea_n_asistentes_ingresados`
8. `test_venta_general_dni_duplicado_devuelve_409`
9. `test_evento_cancelado_bloquea_guardia` — 423
10. `test_evento_cancelado_bloquea_cajera` — 423
11. `test_anotar_en_link_inactivo_devuelve_410`
12. `test_aforo_calcula_correctamente`
13. `test_busqueda_por_qr_y_por_dni`
