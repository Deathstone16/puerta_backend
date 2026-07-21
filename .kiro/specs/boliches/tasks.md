# Plan de implementación — App `boliches`

## Resumen

Implementación incremental de la app `boliches`: modelo, serializer, vistas, URLs, admin y tests. Esta app depende de que `apps.cuentas` esté implementada (modelo `Usuario` con campo `rol` y permiso `IsDueno`).

**Prerequisito:** `apps.cuentas` migrada y con el permiso `IsDueno` disponible en `apps.cuentas.permissions`.

---

## Tareas

- [ ] 1. Crear la app y el modelo `Boliche`
  - Ejecutar `python manage.py startapp boliches` dentro de `api/apps/`
  - Crear `apps/boliches/models.py` con el modelo `Boliche`:
    - `nombre` CharField(200), requerido
    - `direccion` TextField, requerido
    - `dueno` ForeignKey a `settings.AUTH_USER_MODEL`, `on_delete=PROTECT`, `related_name='boliches'`
    - `collector_id_mp` CharField(100), requerido
    - `created_at` DateTimeField auto_now_add
    - `__str__` devuelve `"{nombre} ({dueno.username})"`
    - `Meta.verbose_name` y `verbose_name_plural` en español
  - Agregar `'apps.boliches'` a `INSTALLED_APPS` en `config/settings.py`
  - Ejecutar `python manage.py makemigrations boliches`
  - Ejecutar `python manage.py migrate`
  - _Requisitos: 1.1, 6.1, 6.3_

  - [ ]* 1.1 Test: modelo se crea correctamente
    - Crear `apps/boliches/tests.py`
    - `test_crear_boliche_exitoso_via_orm`: crear Boliche via ORM con todos los campos, verificar que se guarda y `__str__` es correcto
    - _Requisito: 1.1_

- [ ] 2. Registrar en admin
  - Editar `apps/boliches/admin.py`
  - Registrar `Boliche` con `@admin.register(Boliche)` usando `BolicheAdmin(ModelAdmin)`:
    - `list_display = ['nombre', 'dueno', 'collector_id_mp', 'created_at']`
    - `list_filter = ['created_at']`
    - `search_fields = ['nombre', 'dueno__username', 'collector_id_mp']`
    - `readonly_fields = ['created_at']`
  - Verificar que el modelo aparece en `http://localhost:8000/admin/`
  - _Requisito: 6.4_

- [ ] 3. Serializer `BolicheSerializer`
  - Crear `apps/boliches/serializers.py`
  - `BolicheSerializer(ModelSerializer)`:
    - `model = Boliche`
    - `fields = ['id', 'nombre', 'direccion', 'collector_id_mp', 'created_at']`
    - `read_only_fields = ['id', 'created_at']`
    - El campo `dueno` no se incluye en `fields` — se asigna en la vista desde `request.user`
  - _Requisitos: 2.4, 2.5, 5.1, 5.2, 5.3_

  - [ ]* 3.1 Test: serializer no expone el campo `dueno`
    - `test_respuesta_no_incluye_campo_dueno`: serializar un Boliche y verificar que `'dueno'` no está en `serializer.data`
    - `test_collector_id_serializado_como_string`: verificar que el campo se serializa como string
    - _Requisitos: 2.5, 5.2_

- [ ] 4. Vista `POST /api/boliches/` — Crear boliche
  - Crear `apps/boliches/views.py`
  - Implementar `BolichesView(APIView)` con `permission_classes = [IsDueno]`:
    - Método `post(self, request)`:
      1. Verificar si `Boliche.objects.filter(dueno=request.user).exists()` → si sí, devolver 409
      2. Instanciar `BolicheSerializer(data=request.data)`
      3. Si `is_valid()` → `serializer.save(dueno=request.user)` → devolver 201
      4. Si no → devolver 400 con `serializer.errors`
  - _Requisitos: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [ ]* 4.1 Tests de creación
    - `test_crear_boliche_exitoso`: POST con datos válidos como dueño → 201, respuesta tiene `id`, `nombre`, `direccion`, `collector_id_mp`, `created_at`
    - `test_crear_boliche_sin_nombre_devuelve_400`: campo `nombre` faltante → 400
    - `test_crear_segundo_boliche_devuelve_409`: dueño con boliche existente → 409
    - `test_crear_boliche_sin_auth_devuelve_401`: sin token → 401
    - `test_crear_boliche_rol_incorrecto_devuelve_403`: token de rol `guardia` → 403
    - `test_dueno_asignado_desde_request_user`: verificar que el boliche creado tiene `dueno == request.user`, aunque se envíe otro `dueno_id` en el body
    - _Requisitos: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

- [ ] 5. Vista `GET /api/boliches/mio/` — Consultar mi boliche
  - En `apps/boliches/views.py`, agregar `BolicheMioView(APIView)`:
    - `permission_classes = [IsDueno]`
    - Método `get(self, request)`:
      1. `Boliche.objects.get(dueno=request.user)` — si `DoesNotExist` → 404
      2. Devolver `BolicheSerializer(boliche).data` con 200
  - _Requisitos: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 5.1 Tests de consulta
    - `test_obtener_mi_boliche_exitoso`: dueño con boliche → 200, campos correctos
    - `test_obtener_mi_boliche_sin_boliche_devuelve_404`: dueño sin boliche → 404
    - `test_obtener_boliche_sin_auth_devuelve_401`: sin token → 401
    - _Requisitos: 2.1, 2.2, 2.3_

- [ ] 6. Vista `PATCH /api/boliches/:id/` — Editar boliche
  - En `apps/boliches/views.py`, agregar `BolicheDetailView(APIView)`:
    - `permission_classes = [IsDueno]`
    - Método `patch(self, request, pk)`:
      1. `Boliche.objects.get(pk=pk)` — si no existe → 404
      2. Si `boliche.dueno != request.user` → 403
      3. `BolicheSerializer(boliche, data=request.data, partial=True)`
      4. Si válido → `save()`, devolver 200; si no → 400
    - Método `delete(self, request, pk)`: devolver 405 siempre
  - _Requisitos: 3.1, 3.2, 3.3, 3.4, 3.5, 4.1_

  - [ ]* 6.1 Tests de edición
    - `test_patch_boliche_exitoso`: editar `nombre` → 200, campo actualizado en respuesta
    - `test_patch_multiples_campos`: editar `direccion` y `collector_id_mp` juntos → 200
    - `test_patch_boliche_de_otro_dueno_devuelve_403`: dueño B intenta editar boliche de dueño A → 403
    - `test_patch_boliche_inexistente_devuelve_404`: pk que no existe → 404
    - `test_delete_devuelve_405`: DELETE → 405
    - `test_patch_ignora_campo_dueno`: enviar `dueno_id` en el body no cambia el dueño
    - _Requisitos: 3.1, 3.2, 3.3, 3.4, 3.5, 4.1_

- [ ] 7. URLs y registro en el router principal
  - Crear `apps/boliches/urls.py`:
    ```python
    from django.urls import path
    from .views import BolichesView, BolicheMioView, BolicheDetailView

    urlpatterns = [
        path('',          BolichesView.as_view(),    name='boliches-list'),
        path('mio/',      BolicheMioView.as_view(),  name='boliche-mio'),
        path('<int:pk>/', BolicheDetailView.as_view(), name='boliche-detail'),
    ]
    ```
  - En `config/urls.py`, agregar:
    ```python
    path('api/boliches/', include('apps.boliches.urls')),
    ```
  - _Requisito: 6.2_

- [ ] 8. Checkpoint — Verificar funcionamiento completo
  - Ejecutar `python manage.py check` — sin errores
  - Ejecutar `python manage.py test apps.boliches` — todos los tests pasan
  - Probar manualmente con Postman o curl:
    - Login como `carlos_dueno` (fixture) → obtener JWT
    - `POST /api/boliches/` con `{"nombre": "Club Crobar", "direccion": "Av. Figueroa Alcorta 3657, CABA", "collector_id_mp": "123456789"}` → 201
    - `GET /api/boliches/mio/` → 200 con los datos del boliche creado
    - `PATCH /api/boliches/1/` con `{"nombre": "Club Crobar Editado"}` → 200
    - `DELETE /api/boliches/1/` → 405
  - _Todos los requisitos_

---

## Notas

- Las tareas marcadas con `*` son subtareas de testing opcionales que se pueden omitir para acelerar el MVP y completar después.
- El boliche creado en el checkpoint se puede cargar en la fixture `api/fixtures/usuarios_prueba.json` o en un fixture separado `api/fixtures/boliche_prueba.json` para que otros devs tengan datos de prueba completos.
- Una vez que `apps.eventos` esté implementada, el `collector_id_mp` del boliche se usará automáticamente al crear preferencias de pago — no requiere cambios en esta app.
