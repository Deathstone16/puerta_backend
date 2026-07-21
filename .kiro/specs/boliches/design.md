# Documento de Diseño — App `boliches`

## Resumen ejecutivo

La app `boliches` implementa el modelo `Boliche` y sus tres endpoints REST. Es una de las apps más simples del proyecto — su responsabilidad principal es almacenar el `collector_id_mp` del dueño, que otras apps (`pagos`, `eventos`) usan para enrutar cobros y filtrar datos. En el MVP hay exactamente un boliche por dueño.

**Decisiones de diseño principales:**
- Un dueño → un boliche en el MVP (sin lógica multi-boliche)
- `collector_id_mp` como campo de texto simple, no validado contra la API de MP (la validación ocurre al crear la preferencia de pago en `apps.pagos`)
- Sin endpoint de lista general — solo `/api/boliches/mio/` para el dueño autenticado
- Sin DELETE vía API — la integridad referencial con `Evento` hace que eliminar un boliche sea destructivo

---

## Arquitectura

```
┌─────────────────────────────────────────────┐
│  Frontend / Postman                          │
│                                             │
│  POST /api/boliches/                        │
│  GET  /api/boliches/mio/                    │
│  PATCH /api/boliches/:id/                   │
└─────────────┬───────────────────────────────┘
              │ Authorization: Bearer {JWT con rol='dueno'}
              ▼
┌─────────────────────────────────────────────┐
│  IsDueno (apps.cuentas.permissions)         │
│  Verifica request.user.rol == 'dueno'       │
└─────────────┬───────────────────────────────┘
              ▼
┌─────────────────────────────────────────────┐
│  boliches.views                             │
│                                             │
│  BolicheMioView (GET)                       │
│  BolichesView   (POST)                      │
│  BolichesDetailView (PATCH)                 │
└─────────────┬───────────────────────────────┘
              ▼
┌─────────────────────────────────────────────┐
│  BolicheSerializer                          │
│  Campos: id, nombre, direccion,             │
│  collector_id_mp, created_at                │
│  dueno se asigna desde request.user (write) │
│  dueno NO se serializa (read)               │
└─────────────┬───────────────────────────────┘
              ▼
┌─────────────────────────────────────────────┐
│  Boliche (ORM)                              │
│  ↓                                          │
│  Supabase Postgres                          │
└─────────────────────────────────────────────┘
```

---

## Componentes e interfaces

### Modelo `Boliche`

```python
# apps/boliches/models.py
from django.db import models
from django.conf import settings


class Boliche(models.Model):
    nombre          = models.CharField(max_length=200)
    direccion       = models.TextField()
    dueno           = models.ForeignKey(
                          settings.AUTH_USER_MODEL,
                          on_delete=models.PROTECT,
                          related_name='boliches'
                      )
    collector_id_mp = models.CharField(max_length=100)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Boliche'
        verbose_name_plural = 'Boliches'

    def __str__(self):
        return f"{self.nombre} ({self.dueno.username})"
```

**Justificación de `on_delete=PROTECT`:** Si se intenta eliminar un dueño que tiene boliche, Django bloquea la operación. Esto evita orphan records.

**Por qué no hay `unique_together` ni `unique` en `dueno`:** La restricción "un dueño, un boliche" se implementa en la vista, no en el modelo. Esto permite relajar la restricción en el futuro sin migración.

---

### Serializer

```python
# apps/boliches/serializers.py
from rest_framework import serializers
from .models import Boliche


class BolicheSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Boliche
        fields = ['id', 'nombre', 'direccion', 'collector_id_mp', 'created_at']
        read_only_fields = ['id', 'created_at']
```

**Por qué no incluye `dueno`:** El dueño se asigna en la vista desde `request.user`. El frontend no necesita ver ni enviar el objeto usuario — ya sabe quién es porque tiene su JWT.

**`collector_id_mp` como CharField:** No se valida contra la API de MP en esta app. La validación se hace cuando `apps.pagos` intenta crear la preferencia — si el `collector_id_mp` es inválido, el error de MP se propagará en ese momento.

---

### Vistas

```python
# apps/boliches/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from apps.cuentas.permissions import IsDueno
from .models import Boliche
from .serializers import BolicheSerializer


class BolichesView(APIView):
    """POST /api/boliches/ — Crear boliche"""
    permission_classes = [IsDueno]

    def post(self, request):
        # Un dueño, un boliche
        if Boliche.objects.filter(dueno=request.user).exists():
            return Response(
                {'error': 'Ya tenés un boliche registrado.'},
                status=status.HTTP_409_CONFLICT
            )
        serializer = BolicheSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(dueno=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BolicheMioView(APIView):
    """GET /api/boliches/mio/ — Obtener mi boliche"""
    permission_classes = [IsDueno]

    def get(self, request):
        try:
            boliche = Boliche.objects.get(dueno=request.user)
        except Boliche.DoesNotExist:
            return Response(
                {'error': 'No tenés ningún boliche registrado.'},
                status=status.HTTP_404_NOT_FOUND
            )
        return Response(BolicheSerializer(boliche).data)


class BolicheDetailView(APIView):
    """PATCH /api/boliches/:id/ — Editar boliche"""
    permission_classes = [IsDueno]

    def patch(self, request, pk):
        try:
            boliche = Boliche.objects.get(pk=pk)
        except Boliche.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if boliche.dueno != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = BolicheSerializer(boliche, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)
```

---

### URLs

```python
# apps/boliches/urls.py
from django.urls import path
from .views import BolichesView, BolicheMioView, BolicheDetailView

urlpatterns = [
    path('',        BolichesView.as_view(),   name='boliches-list'),
    path('mio/',    BolicheMioView.as_view(),  name='boliche-mio'),
    path('<int:pk>/', BolicheDetailView.as_view(), name='boliche-detail'),
]
```

```python
# En config/urls.py agregar:
path('api/boliches/', include('apps.boliches.urls')),
```

---

### Admin

```python
# apps/boliches/admin.py
from django.contrib import admin
from .models import Boliche


@admin.register(Boliche)
class BolicheAdmin(admin.ModelAdmin):
    list_display  = ['nombre', 'dueno', 'collector_id_mp', 'created_at']
    list_filter   = ['created_at']
    search_fields = ['nombre', 'dueno__username', 'collector_id_mp']
    readonly_fields = ['created_at']
```

---

## Modelo de datos

### `Boliche`

| Campo | Tipo | Restricciones | Descripción |
|-------|------|--------------|-------------|
| `id` | BigAutoField | PK | ID autogenerado |
| `nombre` | CharField(200) | Required | Nombre del local |
| `direccion` | TextField | Required | Dirección física |
| `dueno` | ForeignKey(Usuario) | PROTECT, Required | Dueño del boliche |
| `collector_id_mp` | CharField(100) | Required | ID de cuenta MP del dueño |
| `created_at` | DateTimeField | auto_now_add | Fecha de creación |

**Relaciones con otras apps:**
- `eventos.Evento.boliche` → FK a `Boliche` (una vez que se implemente)
- `rrpp.RRPP.boliche` → FK a `Boliche`

---

## Propiedades de correctitud

### Propiedad 1: Un dueño no puede tener más de un boliche

*Para cualquier* dueño autenticado con un boliche existente, un segundo `POST /api/boliches/` SHALL devolver HTTP 409.

**Valida: Requisito 1.3**

### Propiedad 2: El dueño solo puede editar su propio boliche

*Para cualquier* dueño A y boliche B donde `B.dueno != A`, `PATCH /api/boliches/B.id/` autenticado como A SHALL devolver HTTP 403.

**Valida: Requisito 3.2**

---

## Manejo de errores

| Escenario | Código | Respuesta |
|-----------|--------|-----------|
| Campos requeridos faltantes | 400 | `{"nombre": ["This field is required."]}` |
| Dueño ya tiene boliche | 409 | `{"error": "Ya tenés un boliche registrado."}` |
| Boliche no existe | 404 | `{}` |
| Editar boliche de otro dueño | 403 | `{}` |
| DELETE | 405 | `{}` |
| Sin token | 401 | `{"detail": "Authentication credentials were not provided."}` |
| Token de rol incorrecto | 403 | `{"detail": "You do not have permission to perform this action."}` |

---

## Estrategia de testing

**Tests unitarios en `apps/boliches/tests.py`:**

1. `test_crear_boliche_exitoso` — POST con datos válidos → 201, campos correctos en respuesta
2. `test_crear_boliche_sin_nombre_devuelve_400` — campo requerido faltante
3. `test_crear_segundo_boliche_devuelve_409` — restricción un dueño/un boliche
4. `test_crear_boliche_sin_auth_devuelve_401` — sin token
5. `test_crear_boliche_rol_incorrecto_devuelve_403` — token de guardia intenta crear boliche
6. `test_obtener_mi_boliche_exitoso` — GET devuelve datos del boliche
7. `test_obtener_mi_boliche_sin_boliche_devuelve_404` — dueño sin boliche
8. `test_patch_boliche_exitoso` — edición parcial de nombre
9. `test_patch_boliche_de_otro_dueno_devuelve_403` — protección de recursos
10. `test_patch_boliche_inexistente_devuelve_404`
11. `test_delete_devuelve_405`
12. `test_respuesta_no_incluye_campo_dueno` — el objeto usuario no se expone
13. `test_dueno_asignado_desde_request_user` — no se puede inyectar otro dueño en el body

---

## Dependencias

Esta app depende de:
- `apps.cuentas` — modelo `Usuario` y permiso `IsDueno`

Otras apps dependen de esta:
- `apps.eventos` — `Evento.boliche` FK
- `apps.rrpp` — `RRPP.boliche` FK
- `apps.pagos` — usa `boliche.collector_id_mp` al crear preferencias MP
