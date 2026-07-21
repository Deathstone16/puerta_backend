# Documento de Diseño — App `rrpp`

## Resumen ejecutivo

La app `rrpp` gestiona el módulo de Relaciones Públicas: alta de RRPP, asignación a eventos y generación automática de links. La pieza más delicada es la signal `post_save` en `AsignacionRRPP` que crea exactamente 2 `LinkRRPP` por cada asignación nueva. El panel del RRPP consulta estadísticas en tiempo real desde `apps.puerta.Asistente`.

**Decisiones de diseño principales:**
- Alta de RRPP en `transaction.atomic()` — crea `Usuario` + `RRPP` o ninguno
- Links generados via signal `post_save`, no en la vista — desacopla la lógica de generación
- Estadísticas del panel calculadas en el serializer con queries anotadas, no campos almacenados
- Slugs como UUID4 — imposibles de adivinar, únicos por diseño de la librería estándar

---

## Arquitectura

```
┌──────────────────────────────────────────────────────┐
│  Dueño                                                │
│  GET  /api/rrpp/                                      │
│  POST /api/rrpp/                                      │
│  POST /api/rrpp/:id/asignar-evento/                   │
└──────────────────┬───────────────────────────────────┘
                   │ IsDueno
                   ▼
┌──────────────────────────────────────────────────────┐
│  RRPP                                                 │
│  GET  /api/rrpp/mi-panel/                             │
│  POST /api/rrpp/anotar-invitado/                      │
└──────────────────┬───────────────────────────────────┘
                   │ IsRRPP
                   ▼
┌──────────────────────────────────────────────────────┐
│  rrpp.views                                           │
│  RRPPListCreateView  — GET / POST (IsDueno)           │
│  AsignarEventoView   — POST (IsDueno)                 │
│  MiPanelView         — GET (IsRRPP)                   │
│  AnotarInvitadoView  — POST (IsRRPP)                  │
└──────────────────┬───────────────────────────────────┘
                   ▼
┌──────────────────────────────────────────────────────┐
│  rrpp.models                                          │
│  RRPP ──── AsignacionRRPP ──── LinkRRPP               │
│                │                                      │
│          (signal post_save)                           │
│          crea 2 LinkRRPP automáticamente              │
└──────────────────┬───────────────────────────────────┘
                   ▼
┌──────────────────────────────────────────────────────┐
│  apps.puerta.Asistente (consulta de estadísticas)    │
└──────────────────────────────────────────────────────┘
```

---

## Componentes e interfaces

### Modelos

```python
# apps/rrpp/models.py
import uuid
from django.db import models
from django.conf import settings


class RRPP(models.Model):
    TIPO_COMISION = [
        ('fijo',       'Monto fijo por ingresado'),
        ('porcentaje', 'Porcentaje del recaudado'),
    ]

    usuario        = models.OneToOneField(
                         settings.AUTH_USER_MODEL,
                         on_delete=models.CASCADE,
                         related_name='perfil_rrpp'
                     )
    boliche        = models.ForeignKey(
                         'boliches.Boliche',
                         on_delete=models.PROTECT,
                         related_name='rrpps'
                     )
    tipo_comision  = models.CharField(max_length=20, choices=TIPO_COMISION)
    valor_comision = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = 'RRPP'
        verbose_name_plural = 'RRPPs'

    def __str__(self):
        return f"{self.usuario.get_full_name() or self.usuario.username} — {self.boliche.nombre}"


class AsignacionRRPP(models.Model):
    rrpp   = models.ForeignKey(RRPP, on_delete=models.CASCADE, related_name='asignaciones')
    evento = models.ForeignKey('eventos.Evento', on_delete=models.CASCADE, related_name='asignaciones_rrpp')
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Asignación RRPP'
        verbose_name_plural = 'Asignaciones RRPP'
        unique_together = ('rrpp', 'evento')

    def __str__(self):
        return f"{self.rrpp} → {self.evento.nombre}"


class LinkRRPP(models.Model):
    TIPOS = [('lista', 'Lista'), ('venta_web', 'Venta Web')]

    asignacion = models.ForeignKey(AsignacionRRPP, on_delete=models.CASCADE, related_name='links')
    tipo       = models.CharField(max_length=20, choices=TIPOS)
    slug       = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    activo     = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Link RRPP'
        verbose_name_plural = 'Links RRPP'

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.slug} ({'activo' if self.activo else 'inactivo'})"
```

---

### Signal de generación de links

```python
# apps/rrpp/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import AsignacionRRPP, LinkRRPP


@receiver(post_save, sender=AsignacionRRPP)
def crear_links_rrpp(sender, instance, created, **kwargs):
    """
    Al crear una nueva AsignacionRRPP, genera automáticamente
    2 LinkRRPP: uno de tipo 'lista' y otro de tipo 'venta_web'.
    Solo se ejecuta en la creación (created=True).
    """
    if not created:
        return

    LinkRRPP.objects.bulk_create([
        LinkRRPP(asignacion=instance, tipo='lista'),
        LinkRRPP(asignacion=instance, tipo='venta_web'),
    ])
```

```python
# apps/rrpp/apps.py
from django.apps import AppConfig


class RrppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.rrpp'
    verbose_name = 'RRPP'

    def ready(self):
        import apps.rrpp.signals  # noqa: F401 — registra las signals
```

> **Importante:** `bulk_create` no dispara signals individuales por cada `LinkRRPP`, lo cual es el comportamiento deseado — evita recursión y es más eficiente.

---

### Serializers

```python
# apps/rrpp/serializers.py (estructura)

class LinkRRPPSerializer(ModelSerializer):
    url = SerializerMethodField()
    # get_url: construye la URL pública según tipo
    # lista:     /lista/{slug}/
    # venta_web: /venta/{slug}/

class AsignacionConEstadisticasSerializer(ModelSerializer):
    links       = LinkRRPPSerializer(many=True, read_only=True)
    estadisticas = SerializerMethodField()
    # get_estadisticas: consulta apps.puerta.Asistente filtrando por link_rrpp__asignacion=instance
    # Devuelve: {anotados, ingresados, pendientes, rebotados}

class RRPPSerializer(ModelSerializer):
    nombre     = SerializerMethodField()  # usuario.get_full_name()
    username   = CharField(source='usuario.username')
    asignaciones = AsignacionConEstadisticasSerializer(many=True, read_only=True)

class RRPPCreateSerializer(Serializer):
    # Para el alta: incluye campos de usuario (nombre, apellido, username, password, telefono)
    # más campos de RRPP (tipo_comision, valor_comision)
    # En validate: verifica que username no exista
    # En create: usa transaction.atomic() para crear Usuario + RRPP
```

**Estadísticas del panel — implementación:**

```python
def get_estadisticas(self, asignacion):
    # Import lazy para evitar circular
    from apps.puerta.models import Asistente

    qs = Asistente.objects.filter(link_rrpp__asignacion=asignacion)
    return {
        'anotados':   qs.count(),
        'ingresados': qs.filter(estado='ingresado_final').count(),
        'pendientes': qs.filter(estado__in=['pendiente', 'aprobado_guardia']).count(),
        'rebotados':  qs.filter(estado='rebotado_guardia').count(),
    }
```

---

### Vistas

```python
# apps/rrpp/views.py (estructura)

class RRPPListCreateView(APIView):
    # GET:  IsDueno → filtra RRPP por boliche del dueño autenticado
    # POST: IsDueno → llama RRPPCreateSerializer que hace la transacción atómica

class AsignarEventoView(APIView):
    # POST /api/rrpp/:id/asignar-evento/
    # IsDueno
    # Valida que evento.boliche.dueno == request.user
    # Crea AsignacionRRPP → signal genera 2 links automáticamente
    # Devuelve {asignacion_id, rrpp_nombre, evento_nombre, links: [{tipo, slug, url}]}

class MiPanelView(APIView):
    # GET /api/rrpp/mi-panel/
    # IsRRPP
    # Devuelve asignaciones activas del RRPP autenticado con estadísticas

class AnotarInvitadoView(APIView):
    # POST /api/rrpp/anotar-invitado/
    # IsRRPP
    # Valida que link_rrpp.asignacion.rrpp == request.user.perfil_rrpp
    # Crea Asistente con tipo_ingreso='lista_rrpp', estado='pendiente'
```

---

### Alta de RRPP — transacción atómica

```python
# En RRPPCreateSerializer.create():
from django.db import transaction
from django.contrib.auth import get_user_model

User = get_user_model()

def create(self, validated_data):
    with transaction.atomic():
        user = User.objects.create_user(
            username   = validated_data['username'],
            password   = validated_data['password'],
            first_name = validated_data['nombre'],
            last_name  = validated_data['apellido'],
            email      = validated_data.get('email', ''),
            rol        = 'rrpp',
        )
        rrpp = RRPP.objects.create(
            usuario        = user,
            boliche        = validated_data['boliche'],
            tipo_comision  = validated_data['tipo_comision'],
            valor_comision = validated_data['valor_comision'],
        )
    return rrpp
```

Si `create_user` lanza una excepción (ej: username duplicado), el `atomic()` revierte todo y no queda ningún objeto huérfano.

---

### Desactivación de links al cancelar evento

```python
# apps/rrpp/signals.py — segunda signal
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.eventos.models import Evento


@receiver(post_save, sender=Evento)
def desactivar_links_al_cancelar(sender, instance, **kwargs):
    """Cuando un evento se cancela, desactiva todos sus links de RRPP."""
    if instance.estado == 'cancelado':
        LinkRRPP.objects.filter(
            asignacion__evento=instance
        ).update(activo=False)
```

> Esta signal se puede implementar aquí o en `apps.eventos` como signal post_save. Se coloca en `rrpp` porque es esta app quien gestiona `LinkRRPP`.

---

### URLs

```python
# apps/rrpp/urls.py
from django.urls import path
from .views import RRPPListCreateView, AsignarEventoView, MiPanelView, AnotarInvitadoView

urlpatterns = [
    path('',                         RRPPListCreateView.as_view(), name='rrpp-list-create'),
    path('<int:pk>/asignar-evento/', AsignarEventoView.as_view(),  name='rrpp-asignar-evento'),
    path('mi-panel/',               MiPanelView.as_view(),         name='rrpp-mi-panel'),
    path('anotar-invitado/',        AnotarInvitadoView.as_view(),  name='rrpp-anotar-invitado'),
]

# En config/urls.py:
# path('api/rrpp/', include('apps.rrpp.urls')),
```

---

### Admin

```python
# apps/rrpp/admin.py
class LinkRRPPInline(TabularInline):
    model = LinkRRPP
    extra = 0
    readonly_fields = ['slug', 'activo']

class AsignacionRRPPInline(TabularInline):
    model = AsignacionRRPP
    extra = 0
    inlines = []  # no anidado en admin estándar

@admin.register(RRPP)
class RRPPAdmin(ModelAdmin):
    list_display  = ['usuario', 'boliche', 'tipo_comision', 'valor_comision']
    list_filter   = ['boliche', 'tipo_comision']

@admin.register(AsignacionRRPP)
class AsignacionAdmin(ModelAdmin):
    list_display = ['rrpp', 'evento', 'activa']
    inlines      = [LinkRRPPInline]

@admin.register(LinkRRPP)
class LinkAdmin(ModelAdmin):
    list_display  = ['asignacion', 'tipo', 'slug', 'activo']
    list_filter   = ['tipo', 'activo']
    readonly_fields = ['slug']
```

---

## Modelo de datos

### `RRPP`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | BigAutoField | PK |
| `usuario` | OneToOne(Usuario) | Cuenta de acceso del RRPP |
| `boliche` | FK(Boliche) | Boliche al que pertenece |
| `tipo_comision` | CharField | `fijo` / `porcentaje` |
| `valor_comision` | DecimalField(10,2) | Monto o porcentaje según tipo |

### `AsignacionRRPP`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | BigAutoField | PK |
| `rrpp` | FK(RRPP) | El RRPP asignado |
| `evento` | FK(Evento) | El evento al que se asigna |
| `activa` | Boolean | Default True |
| `unique_together` | (rrpp, evento) | Un RRPP una vez por evento |

### `LinkRRPP`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | BigAutoField | PK |
| `asignacion` | FK(AsignacionRRPP) | Asignación de origen |
| `tipo` | CharField | `lista` / `venta_web` |
| `slug` | UUIDField | UUID4, único global, no editable |
| `activo` | Boolean | False al cancelar el evento |

---

## Propiedades de correctitud

### Propiedad 1: Cada AsignacionRRPP tiene exactamente 2 links

Para cualquier `AsignacionRRPP` recién creada, `LinkRRPP.objects.filter(asignacion=instance).count()` debe ser exactamente 2, con uno de tipo `lista` y uno de tipo `venta_web`.

**Valida: Requisitos 3.2, 8.1**

### Propiedad 2: Alta atómica de RRPP

Si la creación del `Usuario` falla, no debe existir ningún `RRPP` huérfano; y viceversa.

**Valida: Requisito 1.2**

### Propiedad 3: Aislamiento entre RRPPs

Un RRPP nunca puede ver estadísticas ni anotar invitados en links de otro RRPP.

**Valida: Requisitos 4.5, 7.1, 7.2**

---

## Manejo de errores

| Escenario | Código | Mensaje |
|-----------|--------|---------|
| Username duplicado en alta | 400 | `{"username": "Este username ya existe"}` |
| Evento ajeno al asignar | 400 | `{"error": "El evento no pertenece a tu boliche"}` |
| RRPP ya asignado al evento | 409 | `{"error": "El RRPP ya está asignado a este evento"}` |
| Link de otro RRPP al anotar | 403 | `{"error": "Este link no te pertenece"}` |
| Link inactivo al anotar | 410 | `{"error": "Este link está inactivo"}` |
| DNI duplicado en el evento | 409 | `{"error": "Este DNI ya está registrado en el evento"}` |
| Sin auth | 401 | — |
| Rol incorrecto | 403 | — |

---

## Estrategia de testing

**Tests en `apps/rrpp/tests.py`:**

1. `test_alta_rrpp_exitosa_crea_usuario_y_perfil`
2. `test_alta_rrpp_username_duplicado_revierte_transaction`
3. `test_alta_rrpp_sin_auth_devuelve_401`
4. `test_asignar_evento_genera_exactamente_2_links`
5. `test_asignar_evento_links_tienen_slugs_uuid_unicos`
6. `test_asignar_evento_ajeno_devuelve_400`
7. `test_asignar_evento_duplicado_devuelve_409`
8. `test_signal_solo_crea_links_en_creacion_no_en_update`
9. `test_mi_panel_devuelve_solo_asignaciones_propias`
10. `test_mi_panel_estadisticas_en_tiempo_real`
11. `test_anotar_invitado_exitoso`
12. `test_anotar_invitado_link_ajeno_devuelve_403`
13. `test_anotar_invitado_link_inactivo_devuelve_410`
14. `test_anotar_invitado_dni_duplicado_devuelve_409`
15. `test_cancelar_evento_desactiva_links_rrpp`
