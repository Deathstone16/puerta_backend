# Plan de implementación — App `rrpp`

## Resumen

Implementación incremental de la app `rrpp`: modelos, signal de generación de links, alta atómica de RRPP, asignación a eventos, panel del RRPP y anotación de invitados.

**Prerequisitos:**
- `apps.cuentas` migrada con `IsDueno`, `IsRRPP` en `apps.cuentas.permissions`
- `apps.boliches` migrada con modelo `Boliche`
- `apps.eventos` migrada con modelo `Evento`
- `apps.puerta` migrada con modelo `Asistente` (para estadísticas del panel — puede mockearse hasta entonces)

---

## Tareas

- [ ] 1. Crear la app y los tres modelos
  - Ejecutar `python manage.py startapp rrpp` dentro de `api/apps/`
  - Crear `apps/rrpp/models.py` con los tres modelos según el diseño:
    - `RRPP`: `usuario` OneToOne FK a `settings.AUTH_USER_MODEL` (`related_name='perfil_rrpp'`, `on_delete=CASCADE`), `boliche` FK a `'boliches.Boliche'` (`on_delete=PROTECT`, `related_name='rrpps'`), `tipo_comision` CharField choices `fijo`/`porcentaje`, `valor_comision` DecimalField(10,2)
    - `AsignacionRRPP`: `rrpp` FK, `evento` FK a `'eventos.Evento'`, `activa` BooleanField default=True, `unique_together = ('rrpp', 'evento')`
    - `LinkRRPP`: `asignacion` FK, `tipo` CharField choices `lista`/`venta_web`, `slug` UUIDField(default=uuid.uuid4, unique=True, editable=False), `activo` BooleanField default=True
  - Reemplazar el contenido de `apps/rrpp/apps.py` para que `RrppConfig.ready()` importe `apps.rrpp.signals`
  - Agregar `'apps.rrpp'` a `INSTALLED_APPS` en `config/settings.py`
  - Ejecutar `python manage.py makemigrations rrpp` y `python manage.py migrate`
  - _Requisitos: 1.1, 3.2, 8.1_

  - [ ]* 1.1 Test: modelos se crean correctamente vía ORM
    - Crear `apps/rrpp/tests.py`
    - `test_crear_rrpp_via_orm`: crear Usuario con rol=rrpp + RRPP, verificar `__str__` y `perfil_rrpp` reverse relation
    - `test_unique_together_asignacion`: crear AsignacionRRPP duplicada → IntegrityError
    - `test_slug_uuid_no_editable`: verificar que `LinkRRPP.slug` es UUID y se genera automáticamente
    - _Requisitos: 1.1, 3.3_

- [ ] 2. Signal `post_save` — generación automática de links
  - Crear `apps/rrpp/signals.py` con dos signals:
    - **Signal 1** — `crear_links_rrpp`: receptor de `post_save` en `AsignacionRRPP`. Si `created=True`, crea exactamente 2 `LinkRRPP` via `bulk_create`: uno de tipo `'lista'` y otro de tipo `'venta_web'`. Si `created=False`, no hace nada.
    - **Signal 2** — `desactivar_links_al_cancelar`: receptor de `post_save` en `Evento`. Si `instance.estado == 'cancelado'`, ejecuta `LinkRRPP.objects.filter(asignacion__evento=instance).update(activo=False)`
  - Verificar que `apps/rrpp/apps.py` importa `apps.rrpp.signals` en `ready()`
  - _Requisitos: 3.2, 6.1, 6.3, 8.1, 8.2, 8.3_

  - [ ]* 2.1 Tests de signals
    - `test_asignacion_nueva_genera_exactamente_2_links`: crear AsignacionRRPP → verificar `LinkRRPP.objects.filter(asignacion=a).count() == 2`
    - `test_asignacion_nueva_genera_un_lista_y_un_venta_web`: verificar tipos
    - `test_signal_no_crea_links_en_update`: guardar de nuevo la asignación → sigue habiendo 2 links
    - `test_cancelar_evento_desactiva_links_rrpp`: cambiar evento.estado a 'cancelado', save() → todos los links del evento quedan activo=False
    - _Requisitos: 3.2, 6.1, 6.3, 8.1, 8.2, 8.3_

- [ ] 3. Admin de Django
  - Editar `apps/rrpp/admin.py`:
    - `LinkRRPPInline(TabularInline)`: modelo `LinkRRPP`, `extra=0`, `readonly_fields=['slug', 'activo']`
    - `@admin.register(RRPP)` con `list_display=['usuario', 'boliche', 'tipo_comision', 'valor_comision']`, `list_filter=['boliche', 'tipo_comision']`
    - `@admin.register(AsignacionRRPP)` con `list_display=['rrpp', 'evento', 'activa']`, `inlines=[LinkRRPPInline]`
    - `@admin.register(LinkRRPP)` con `list_display=['asignacion', 'tipo', 'slug', 'activo']`, `list_filter=['tipo', 'activo']`, `readonly_fields=['slug']`
  - _Requisito: (admin para debug manual)_

- [ ] 4. Serializer y vista `POST /api/rrpp/` — Alta de RRPP
  - Crear `apps/rrpp/serializers.py`
  - `RRPPCreateSerializer(Serializer)`:
    - Campos de entrada: `nombre`, `apellido`, `username`, `password` (write_only), `telefono` (opcional), `tipo_comision`, `valor_comision`
    - `validate_username`: verificar que no existe → `raise ValidationError` si existe
    - `create(validated_data)`: dentro de `transaction.atomic()`, llamar `User.objects.create_user(...)` con `rol='rrpp'` y luego `RRPP.objects.create(...)`. Si cualquier paso falla, el `atomic()` revierte todo.
    - El campo `boliche` se inyecta desde la vista (no viene del body del request)
  - Crear `apps/rrpp/views.py`
  - `RRPPListCreateView(APIView)`:
    - `permission_classes = [IsDueno]`
    - `get`: obtener boliche del dueño autenticado, filtrar `RRPP.objects.filter(boliche=boliche)`, serializar con `RRPPSerializer`
    - `post`: instanciar `RRPPCreateSerializer(data=request.data)`, si válido llamar `serializer.save(boliche=boliche_del_dueno)`, devolver 201
  - _Requisitos: 1.1–1.6, 2.1–2.3_

  - [ ]* 4.1 Tests de alta y listado
    - `test_alta_rrpp_exitosa_crea_usuario_y_perfil`: POST → 201, existe Usuario con rol=rrpp y RRPP asociado
    - `test_alta_rrpp_username_duplicado_revierte_transaction`: POST con username existente → 400, no se crea RRPP huérfano
    - `test_alta_rrpp_campos_faltantes_devuelve_400`
    - `test_alta_rrpp_sin_auth_devuelve_401`
    - `test_alta_rrpp_rol_incorrecto_devuelve_403`
    - `test_listado_rrpp_solo_muestra_los_del_boliche_propio`
    - _Requisitos: 1.1–1.6, 2.1–2.3_

- [ ] 5. Vista `POST /api/rrpp/:id/asignar-evento/` — Asignación
  - `AsignarEventoView(APIView)`:
    - `permission_classes = [IsDueno]`
    - Método `post(self, request, pk)`:
      1. Obtener `rrpp = get_object_or_404(RRPP, pk=pk)` — verificar que pertenece al boliche del dueño
      2. Obtener `evento_id` del body
      3. Obtener `evento = get_object_or_404(Evento, pk=evento_id)` — si `evento.boliche.dueno != request.user` → 400 `{"error": "El evento no pertenece a tu boliche"}`
      4. Si ya existe `AsignacionRRPP.objects.filter(rrpp=rrpp, evento=evento).exists()` → 409
      5. `asignacion = AsignacionRRPP.objects.create(rrpp=rrpp, evento=evento)` — la signal genera los 2 links automáticamente
      6. Recargar los links: `asignacion.links.all()`
      7. Devolver 201 con `{asignacion_id, rrpp_nombre, evento_nombre, links: [{tipo, slug, url}]}`
  - El campo `url` de cada link se construye así:
    - tipo `lista`: `f"/lista/{link.slug}/"`
    - tipo `venta_web`: `f"/venta/{link.slug}/"`
  - _Requisitos: 3.1–3.6_

  - [ ]* 5.1 Tests de asignación
    - `test_asignar_evento_genera_2_links_en_respuesta`
    - `test_asignar_evento_links_tienen_slugs_distintos`
    - `test_asignar_evento_ajeno_al_boliche_devuelve_400`
    - `test_asignar_evento_duplicado_devuelve_409`
    - `test_asignar_sin_auth_devuelve_401`
    - _Requisitos: 3.1–3.6_

- [ ] 6. Serializer `RRPPSerializer` con asignaciones anidadas
  - `LinkRRPPSerializer(ModelSerializer)`:
    - `fields = ['tipo', 'slug', 'activo']`
    - Campo `url` como `SerializerMethodField` que construye la URL pública
  - `AsignacionConEstadisticasSerializer(ModelSerializer)`:
    - `fields = ['id', 'evento_id', 'evento_nombre', 'evento_fecha', 'color_pulsera', 'activa', 'links', 'estadisticas']`
    - `links = LinkRRPPSerializer(many=True, read_only=True)`
    - `estadisticas = SerializerMethodField()` — consulta `apps.puerta.Asistente` via lazy import
    - Si `apps.puerta` no está disponible aún, devolver `{'anotados': 0, 'ingresados': 0, 'pendientes': 0, 'rebotados': 0}`
  - `RRPPSerializer(ModelSerializer)`:
    - `fields = ['id', 'nombre', 'username', 'tipo_comision', 'valor_comision', 'asignaciones']`
    - `nombre` como `SerializerMethodField` → `usuario.get_full_name() or usuario.username`
    - `username` como `CharField(source='usuario.username', read_only=True)`
    - `asignaciones = AsignacionConEstadisticasSerializer(many=True, read_only=True)`
  - _Requisitos: 2.2, 4.2, 4.3_

- [ ] 7. Vista `GET /api/rrpp/mi-panel/` — Panel del RRPP
  - `MiPanelView(APIView)`:
    - `permission_classes = [IsRRPP]`
    - Método `get(self, request)`:
      1. Obtener `rrpp = get_object_or_404(RRPP, usuario=request.user)`
      2. `asignaciones = AsignacionRRPP.objects.filter(rrpp=rrpp, activa=True).select_related('evento').prefetch_related('links')`
      3. Serializar con `AsignacionConEstadisticasSerializer(asignaciones, many=True)`
      4. Devolver 200
  - _Requisitos: 4.1–4.5, 7.2_

  - [ ]* 7.1 Tests del panel
    - `test_mi_panel_devuelve_solo_asignaciones_propias`: dos RRPPs distintos, cada uno ve solo las suyas
    - `test_mi_panel_estadisticas_en_tiempo_real`: crear Asistentes con distintos estados, verificar conteos
    - `test_mi_panel_sin_auth_devuelve_401`
    - `test_mi_panel_rol_incorrecto_devuelve_403`
    - _Requisitos: 4.1–4.5, 7.2_

- [ ] 8. Vista `POST /api/rrpp/anotar-invitado/` — Carga manual
  - `AnotarInvitadoView(APIView)`:
    - `permission_classes = [IsRRPP]`
    - Método `post(self, request)`:
      1. Obtener `slug_lista` del body
      2. `link = get_object_or_404(LinkRRPP, slug=slug_lista, tipo='lista')`
      3. Si `link.asignacion.rrpp.usuario != request.user` → 403 `{"error": "Este link no te pertenece"}`
      4. Si `not link.activo` → 410 `{"error": "Este link está inactivo"}`
      5. Validar campos `nombre`, `apellido`, `dni` — si falta alguno → 400
      6. Verificar que no existe Asistente con mismo DNI en el mismo evento → si existe → 409
      7. Crear Asistente via import lazy de `apps.puerta.models`:
         ```python
         from apps.puerta.models import Asistente
         Asistente.objects.create(
             evento=link.asignacion.evento,
             link_rrpp=link,
             nombre=nombre, apellido=apellido, dni=dni,
             tipo_ingreso='lista_rrpp',
             estado='pendiente',
         )
         ```
      8. Devolver 201 `{id, nombre, apellido, dni, estado}`
  - _Requisitos: 5.1–5.5, 7.1_

  - [ ]* 8.1 Tests de anotación
    - `test_anotar_invitado_exitoso`
    - `test_anotar_invitado_link_de_otro_rrpp_devuelve_403`
    - `test_anotar_invitado_link_inactivo_devuelve_410`
    - `test_anotar_invitado_dni_duplicado_devuelve_409`
    - `test_anotar_invitado_campos_faltantes_devuelve_400`
    - _Requisitos: 5.1–5.5, 7.1_

- [ ] 9. URLs y registro en el router principal
  - Crear `apps/rrpp/urls.py`:
    ```python
    from django.urls import path
    from .views import RRPPListCreateView, AsignarEventoView, MiPanelView, AnotarInvitadoView

    urlpatterns = [
        path('',                         RRPPListCreateView.as_view(), name='rrpp-list-create'),
        path('<int:pk>/asignar-evento/', AsignarEventoView.as_view(),  name='rrpp-asignar-evento'),
        path('mi-panel/',               MiPanelView.as_view(),         name='rrpp-mi-panel'),
        path('anotar-invitado/',        AnotarInvitadoView.as_view(),  name='rrpp-anotar-invitado'),
    ]
    ```
  - En `config/urls.py` agregar: `path('api/rrpp/', include('apps.rrpp.urls'))`
  - _Requisitos: todos_

- [ ] 10. Checkpoint final
  - `python manage.py check` — sin errores
  - `python manage.py test apps.rrpp` — todos los tests pasan
  - Flujo manual con Postman:
    1. Login como `carlos_dueno` → JWT
    2. `POST /api/rrpp/` → crear RRPP "Juan Pérez"
    3. `POST /api/rrpp/1/asignar-evento/` con evento de prueba → ver 2 links en la respuesta
    4. Login como `juan_rrpp` → `GET /api/rrpp/mi-panel/` → ver estadísticas en cero
    5. `POST /api/rrpp/anotar-invitado/` con el slug del link de lista → asistente creado
    6. `GET /api/rrpp/mi-panel/` → estadísticas muestran 1 anotado

---

## Notas

- Las subtareas marcadas con `*` son opcionales para el MVP
- El lazy import de `apps.puerta.models` en el serializer de estadísticas y en `AnotarInvitadoView` evita imports circulares — `rrpp` y `puerta` se referencian mutuamente
- Una vez que `apps.puerta` esté implementada, no hay nada que cambiar en esta app — el import funciona automáticamente
