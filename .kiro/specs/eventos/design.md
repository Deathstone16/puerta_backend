# Documento de Diseño — App `eventos`

## Resumen ejecutivo

La app `eventos` gestiona el ciclo de vida de los eventos de boliche: creación, edición, cancelación y consulta pública. Su pieza más importante es la función `calcular_precio_publicado()` que aplica los fees de MP y Norware al precio base definido por el dueño. Los eventos nunca se eliminan — se cancelan, lo que bloquea edición futura y dispara reembolsos en `apps.pagos`.

**Decisiones de diseño principales:**
- `precio_publicado` se calcula en el serializer, no se persiste en la DB — siempre refleja los fees actuales del settings
- Acoplamiento débil con `apps.pagos`: la cancelación intenta importar `reembolsar_evento` dinámicamente; si no existe, loguea y continúa sin fallar
- `DELETE` bloqueado a nivel de vista, no a nivel de modelo — más explícito para el desarrollador
- Un solo serializer con un campo `desglose_precio` adicional para el detalle (no crear dos serializers separados)

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│  Público / Dueño                                         │
│                                                          │
│  GET  /api/eventos/                                      │
│  GET  /api/eventos/:id/                                  │
│  POST /api/eventos/             (IsDueno)                │
│  PATCH /api/eventos/:id/        (IsDueno)                │
│  POST /api/eventos/:id/cancelar/ (IsDueno)               │
│  GET  /api/precios/calcular/                             │
└──────────────────┬──────────────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────────────┐
│  eventos.views                                           │
│                                                          │
│  EventoListView       — GET lista pública               │
│  EventoDetailView     — GET detalle + PATCH + DELETE    │
│  EventoCreateView     — POST (IsDueno)                   │
│  EventoCancelarView   — POST (IsDueno)                   │
│  CalcularPrecioView   — GET público                      │
└──────────────────┬──────────────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────────────┐
│  eventos.serializers                                     │
│                                                          │
│  EventoListSerializer   — campos mínimos para la lista  │
│  EventoDetailSerializer — todos los campos + desglose   │
└──────────────────┬──────────────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────────────┐
│  eventos.utils.calcular_precio_publicado(precio_base)   │
│  Lee FEE_MP_PCT y NORWARE_FEE_PCT de settings           │
│  Aritmética Decimal + ROUND_HALF_UP                     │
└──────────────────┬──────────────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────────────┐
│  Evento (ORM) → Supabase Postgres                        │
└─────────────────────────────────────────────────────────┘
```

---

## Componentes e interfaces

### Modelo `Evento`

```python
# apps/eventos/models.py
from django.db import models


class Evento(models.Model):
    ESTADOS = [('activo', 'Activo'), ('cancelado', 'Cancelado')]

    boliche            = models.ForeignKey(
                             'boliches.Boliche',
                             on_delete=models.PROTECT,
                             related_name='eventos'
                         )
    nombre             = models.CharField(max_length=200)
    fecha              = models.DateTimeField()
    aforo_max          = models.PositiveIntegerField()
    color_pulsera      = models.CharField(max_length=50)
    precio_base        = models.DecimalField(max_digits=10, decimal_places=2)
    line_up            = models.JSONField(default=list)
    estado             = models.CharField(max_length=20, choices=ESTADOS, default='activo')
    motivo_cancelacion = models.TextField(blank=True, null=True)
    created_at         = models.DateTimeField(auto_now_add=True)
    updated_at         = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Evento'
        verbose_name_plural = 'Eventos'
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.nombre} — {self.fecha.strftime('%d/%m/%Y')} ({self.estado})"
```

---

### Función utilitaria `calcular_precio_publicado`

```python
# apps/eventos/utils.py
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings


def calcular_precio_publicado(precio_base):
    """
    Calcula el precio que paga el asistente sumando los fees de MP y Norware.

    Args:
        precio_base: número positivo (int, float o Decimal)

    Returns:
        dict con precio_base (int), fee_mp (float), fee_norware (float),
        precio_publicado (int)

    Raises:
        ValueError: si precio_base no es numérico o es <= 0
    """
    try:
        base = Decimal(str(precio_base))
    except Exception:
        raise ValueError(f"precio_base debe ser un número válido, recibido: {precio_base!r}")

    if base <= 0:
        raise ValueError(f"precio_base debe ser mayor a cero, recibido: {base}")

    fee_mp_pct    = Decimal(str(settings.FEE_MP_PCT))
    norware_pct   = Decimal(str(settings.NORWARE_FEE_PCT))

    fee_mp        = (base * fee_mp_pct / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    fee_norware   = (base * norware_pct / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    precio_pub    = (base + fee_mp + fee_norware).quantize(Decimal('1'), rounding=ROUND_HALF_UP)

    return {
        'precio_base':      int(base),
        'fee_mp':           float(fee_mp),
        'fee_norware':      float(fee_norware),
        'precio_publicado': int(precio_pub),
    }
```

---

### Serializers

```python
# apps/eventos/serializers.py
from rest_framework import serializers
from .models import Evento
from .utils import calcular_precio_publicado


class BolicheResumenSerializer(serializers.Serializer):
    id        = serializers.IntegerField()
    nombre    = serializers.CharField()
    direccion = serializers.CharField()


class EventoListSerializer(serializers.ModelSerializer):
    precio_publicado = serializers.SerializerMethodField()
    boliche          = BolicheResumenSerializer(read_only=True)
    boliche_id       = serializers.PrimaryKeyRelatedField(
                           source='boliche',
                           queryset=__import__('apps.boliches.models', fromlist=['Boliche']).Boliche.objects.all(),
                           write_only=True
                       )

    class Meta:
        model  = Evento
        fields = [
            'id', 'nombre', 'fecha', 'color_pulsera',
            'precio_base', 'precio_publicado', 'aforo_max',
            'estado', 'boliche', 'boliche_id',
        ]
        read_only_fields = ['id', 'estado']

    def get_precio_publicado(self, obj):
        return calcular_precio_publicado(obj.precio_base)['precio_publicado']


class EventoDetailSerializer(EventoListSerializer):
    desglose_precio = serializers.SerializerMethodField()

    class Meta(EventoListSerializer.Meta):
        fields = EventoListSerializer.Meta.fields + [
            'line_up', 'desglose_precio',
            'motivo_cancelacion', 'created_at', 'updated_at',
        ]
        read_only_fields = EventoListSerializer.Meta.read_only_fields + [
            'motivo_cancelacion', 'created_at', 'updated_at',
        ]

    def get_desglose_precio(self, obj):
        return calcular_precio_publicado(obj.precio_base)
```

> **Nota de implementación:** el import de `Boliche` dentro del campo es un workaround para evitar imports circulares. La implementación real debe usar `from apps.boliches.models import Boliche` en la parte superior del archivo — el pseudo-código de arriba es solo ilustrativo.

---

### Vistas

```python
# apps/eventos/views.py (estructura)

class EventoListView(ListAPIView):
    # GET /api/eventos/ — público
    permission_classes = [AllowAny]
    serializer_class   = EventoListSerializer
    # Filtra por ?estado= si se provee

class EventoCreateView(CreateAPIView):
    # POST /api/eventos/ — IsDueno
    permission_classes = [IsDueno]
    serializer_class   = EventoDetailSerializer
    # Valida que boliche.dueno == request.user en perform_create

class EventoDetailView(RetrieveUpdateAPIView):
    # GET /api/eventos/:id/ — público
    # PATCH /api/eventos/:id/ — IsDueno
    # Bloquea PATCH si estado == 'cancelado' → 405
    # Bloquea DELETE siempre → 405
    # Valida que boliche.dueno == request.user en update

class EventoCancelarView(APIView):
    # POST /api/eventos/:id/cancelar/ — IsDueno
    # Valida motivo no vacío
    # Cambia estado → 'cancelado'
    # Intenta importar y llamar reembolsar_evento dinámicamente
    # Devuelve {id, estado, motivo_cancelacion, reembolsos_iniciados}

class CalcularPrecioView(APIView):
    # GET /api/precios/calcular/?precio_base=X — público
    permission_classes = [AllowAny]
```

**Lógica de cancelación con acoplamiento débil:**

```python
def _intentar_reembolso(evento_id):
    """Intenta llamar a reembolsar_evento de apps.pagos. 
    Si el módulo no está disponible, loguea y devuelve 0."""
    try:
        from apps.pagos.services import reembolsar_evento
        return reembolsar_evento(evento_id)
    except ImportError:
        import logging
        logging.getLogger(__name__).warning(
            "apps.pagos.services no disponible. Reembolsos no procesados para evento %s", evento_id
        )
        return 0
```

---

### URLs

```python
# apps/eventos/urls.py
from django.urls import path
from .views import (
    EventoListView, EventoCreateView, EventoDetailView,
    EventoCancelarView, CalcularPrecioView
)

urlpatterns = [
    path('',              EventoListView.as_view(),    name='evento-list'),
    path('crear/',        EventoCreateView.as_view(),  name='evento-create'),
    path('<int:pk>/',     EventoDetailView.as_view(),  name='evento-detail'),
    path('<int:pk>/cancelar/', EventoCancelarView.as_view(), name='evento-cancelar'),
]

# En config/urls.py:
# path('api/eventos/', include('apps.eventos.urls')),
# path('api/precios/', include('apps.eventos.precio_urls')),  ← archivo separado para calcular/
```

---

### Admin

```python
# apps/eventos/admin.py
@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display   = ['nombre', 'boliche', 'fecha', 'estado', 'precio_base', 'aforo_max']
    list_filter    = ['estado', 'boliche', 'fecha']
    search_fields  = ['nombre']
    readonly_fields = ['created_at', 'updated_at', 'motivo_cancelacion']
    date_hierarchy = 'fecha'
```

---

## Modelo de datos

### `Evento`

| Campo | Tipo | Restricciones | Descripción |
|-------|------|--------------|-------------|
| `id` | BigAutoField | PK | ID autogenerado |
| `boliche` | FK(Boliche) | PROTECT | Boliche al que pertenece |
| `nombre` | CharField(200) | Required | Nombre de la noche |
| `fecha` | DateTimeField | Required | Fecha y hora del evento |
| `aforo_max` | PositiveIntegerField | Required, > 0 | Capacidad máxima |
| `color_pulsera` | CharField(50) | Required | Color real de la noche |
| `precio_base` | DecimalField(10,2) | Required, > 0 | Precio sin fees |
| `line_up` | JSONField | Default: [] | Artistas y horarios |
| `estado` | CharField(20) | choices, default: activo | activo / cancelado |
| `motivo_cancelacion` | TextField | null, blank | Solo si cancelado |
| `created_at` | DateTimeField | auto_now_add | — |
| `updated_at` | DateTimeField | auto_now | — |

---

## Propiedades de correctitud

### Propiedad 1: precio_publicado es siempre consistente con precio_base y fees

Para cualquier `Evento` con `precio_base = B`, `precio_publicado` serializado debe ser igual a `calcular_precio_publicado(B)['precio_publicado']`.

**Valida: Requisito 2.1, 5.5**

### Propiedad 2: Evento cancelado no puede editarse

Para cualquier `Evento` con `estado = 'cancelado'`, `PATCH /api/eventos/:id/` debe devolver 405.

**Valida: Requisito 6.3, 7.6**

### Propiedad 3: Solo el dueño del boliche puede crear/editar/cancelar su evento

Para cualquier dueño A que intenta operar sobre un evento cuyo `boliche.dueno != A`, la respuesta debe ser 403.

**Valida: Requisitos 5.2, 6.2, 7.5**

---

## Manejo de errores

| Escenario | Código | Descripción |
|-----------|--------|-------------|
| precio_base <= 0 | 400 | Validación en serializer |
| aforo_max == 0 | 400 | PositiveIntegerField lo bloquea |
| Evento no encontrado | 404 | — |
| PATCH de evento cancelado | 405 | "No se puede editar un evento cancelado" |
| DELETE | 405 | "Método no permitido" |
| Cancelar sin motivo | 400 | "El campo motivo es obligatorio" |
| Cancelar evento ya cancelado | 409 | "El evento ya está cancelado" |
| Operar sobre evento de otro dueño | 403 | — |
| precio_base no numérico en calcular/ | 400 | "precio_base debe ser un número válido" |

---

## Estrategia de testing

**Tests en `apps/eventos/tests.py`:**

1. `test_calcular_precio_con_fees_default` — verificar aritmética con valores conocidos
2. `test_calcular_precio_base_cero_lanza_error` — ValueError
3. `test_calcular_precio_base_no_numerico_lanza_error` — ValueError
4. `test_listado_publico_sin_auth` — GET lista → 200
5. `test_listado_filtra_por_estado` — ?estado=activo solo trae activos
6. `test_detalle_incluye_desglose` — GET :id/ tiene desglose_precio
7. `test_crear_evento_como_dueno` — POST → 201 con precio_publicado calculado
8. `test_crear_evento_boliche_ajeno_devuelve_403` — dueño B intenta crear en boliche de A
9. `test_patch_evento_activo` — edición parcial → 200
10. `test_patch_evento_cancelado_devuelve_405` — estado bloqueado
11. `test_cancelar_sin_motivo_devuelve_400` — validación
12. `test_cancelar_exitoso` — estado cambia a cancelado
13. `test_cancelar_ya_cancelado_devuelve_409` — idempotencia
14. `test_delete_devuelve_405` — siempre
15. `test_calcular_precio_endpoint` — GET /api/precios/calcular/?precio_base=5000
16. `test_calcular_precio_sin_param_devuelve_400`
