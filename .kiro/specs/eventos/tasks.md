# Plan de implementación — App `eventos`

## Resumen

Implementación incremental de la app `eventos`: utilidad de cálculo de precios, modelo, serializers, vistas, URLs, admin y tests. Depende de `apps.cuentas` (permiso `IsDueno`) y `apps.boliches` (modelo `Boliche`).

**Prerequisitos:**
- `apps.cuentas` migrada con permiso `IsDueno` en `apps.cuentas.permissions`
- `apps.boliches` migrada con modelo `Boliche`
- `settings.py` con `FEE_MP_PCT` y `NORWARE_FEE_PCT` leídos de `.env`

---

## Tareas

- [ ] 1. Configurar variables de fees en settings y crear la app
  - Ejecutar `python manage.py startapp eventos` dentro de `api/apps/`
  - Agregar `'apps.eventos'` a `INSTALLED_APPS` en `config/settings.py`
  - Agregar en `config/settings.py` (si no existen):
    ```python
    from decouple import config
    FEE_MP_PCT     = config('FEE_MP_PCT',     default=5.99, cast=float)
    NORWARE_FEE_PCT = config('NORWARE_FEE_PCT', default=8.0,  cast=float)
    ```
  - Verificar que `.env.example` tiene ambas variables documentadas
  - _Requisitos: 2.2, 2.6, 10.1, 10.3_

- [ ] 2. Función `calcular_precio_publicado` en `eventos/utils.py`
  - Crear `apps/eventos/utils.py`
  - Implementar `calcular_precio_publicado(precio_base)`:
    - Convertir `precio_base` a `Decimal` via `Decimal(str(precio_base))` — si falla, `raise ValueError`
    - Si `precio_base <= 0`, `raise ValueError`
    - Leer `settings.FEE_MP_PCT` y `settings.NORWARE_FEE_PCT` como `Decimal`
    - Calcular `fee_mp` y `fee_norware` con `.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)`
    - Calcular `precio_publicado` como `(base + fee_mp + fee_norware).quantize(Decimal('1'), rounding=ROUND_HALF_UP)`
    - Devolver `{'precio_base': int, 'fee_mp': float, 'fee_norware': float, 'precio_publicado': int}`
  - _Requisitos: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [ ]* 2.1 Tests de la función utilitaria
    - Crear `apps/eventos/tests.py`
    - `test_calcular_precio_con_fees_default`: con `precio_base=10000`, `FEE_MP_PCT=5.99`, `NORWARE_FEE_PCT=8.0` → `precio_publicado=14399` (verificar aritmética exacta)
    - `test_calcular_precio_redondeo_correcto`: verificar que usa ROUND_HALF_UP
    - `test_calcular_precio_base_cero_lanza_value_error`
    - `test_calcular_precio_base_negativo_lanza_value_error`
    - `test_calcular_precio_base_no_numerico_lanza_value_error`
    - `test_calcular_precio_lee_fees_de_settings`: usar `@override_settings` para cambiar fees y verificar que el resultado cambia
    - _Requisitos: 2.1, 2.3, 2.4, 2.5_

- [ ] 3. Modelo `Evento` y migración
  - Crear `apps/eventos/models.py` con el modelo `Evento` según el diseño:
    - `boliche` FK a `'boliches.Boliche'`, `on_delete=PROTECT`, `related_name='eventos'`
    - `nombre` CharField(200)
    - `fecha` DateTimeField
    - `aforo_max` PositiveIntegerField
    - `color_pulsera` CharField(50)
    - `precio_base` DecimalField(max_digits=10, decimal_places=2)
    - `line_up` JSONField(default=list)
    - `estado` CharField(max_length=20, choices=[('activo','Activo'),('cancelado','Cancelado')], default='activo')
    - `motivo_cancelacion` TextField(blank=True, null=True)
    - `created_at` DateTimeField(auto_now_add=True)
    - `updated_at` DateTimeField(auto_now=True)
    - `Meta.ordering = ['-fecha']`
    - `__str__` devuelve `"{nombre} — {fecha strftime('%d/%m/%Y')} ({estado})"`
  - Ejecutar `python manage.py makemigrations eventos` y `python manage.py migrate`
  - _Requisito: 1.1, 1.2, 1.3_

- [ ] 4. Admin de Django para `Evento`
  - Editar `apps/eventos/admin.py`:
    - `@admin.register(Evento)` con `EventoAdmin(ModelAdmin)`
    - `list_display = ['nombre', 'boliche', 'fecha', 'estado', 'precio_base', 'aforo_max']`
    - `list_filter = ['estado', 'boliche', 'fecha']`
    - `search_fields = ['nombre']`
    - `readonly_fields = ['created_at', 'updated_at', 'motivo_cancelacion']`
    - `date_hierarchy = 'fecha'`
  - Verificar que el modelo aparece en el admin y se puede crear un evento de prueba
  - _Requisito: 1.4_

- [ ] 5. Serializers `EventoListSerializer` y `EventoDetailSerializer`
  - Crear `apps/eventos/serializers.py`
  - `BolicheResumenSerializer(Serializer)`: campos `id`, `nombre`, `direccion` (read-only, anidado)
  - `EventoListSerializer(ModelSerializer)`:
    - `fields`: `id`, `nombre`, `fecha`, `color_pulsera`, `precio_base`, `precio_publicado`, `aforo_max`, `estado`, `boliche` (read), `boliche_id` (write-only, PrimaryKeyRelatedField)
    - `precio_publicado` como `SerializerMethodField` que llama a `calcular_precio_publicado`
    - `read_only_fields`: `id`, `estado`
  - `EventoDetailSerializer(EventoListSerializer)`:
    - Agrega: `line_up`, `desglose_precio` (SerializerMethodField), `motivo_cancelacion`, `created_at`, `updated_at`
    - `get_desglose_precio` devuelve el dict completo de `calcular_precio_publicado`
  - _Requisitos: 3.1, 4.1, 5.5_

- [ ] 6. Vista pública — Listado y detalle
  - Crear `apps/eventos/views.py`
  - `EventoListView(ListAPIView)`:
    - `permission_classes = [AllowAny]`
    - `serializer_class = EventoListSerializer`
    - `queryset = Evento.objects.select_related('boliche').all()`
    - Filtrar por `?estado=` si está presente en `request.query_params`
  - `EventoDetailView(RetrieveUpdateAPIView)`:
    - GET: `permission_classes = [AllowAny]`, `serializer_class = EventoDetailSerializer`
    - PATCH: verificar `IsDueno` y que `boliche.dueno == request.user`; si `estado == 'cancelado'` → 405
    - `delete()`: siempre devuelve 405
  - _Requisitos: 3.1–3.5, 4.1–4.3, 6.1–6.5, 8.1, 8.2_

  - [ ]* 6.1 Tests de listado y detalle
    - `test_listado_publico_sin_auth`: GET /api/eventos/ → 200
    - `test_listado_filtra_por_estado_activo`: ?estado=activo solo trae activos
    - `test_listado_filtra_por_estado_cancelado`: ?estado=cancelado
    - `test_listado_sin_filtro_trae_todos`
    - `test_detalle_incluye_desglose_precio`: campos fee_mp, fee_norware, precio_publicado presentes
    - `test_detalle_incluye_line_up`
    - `test_detalle_evento_inexistente_devuelve_404`
    - `test_delete_devuelve_405`
    - _Requisitos: 3.1–3.5, 4.1–4.3, 8.1, 8.2_

- [ ] 7. Vista `POST /api/eventos/` — Crear evento
  - `EventoCreateView(CreateAPIView)`:
    - `permission_classes = [IsDueno]`
    - `serializer_class = EventoDetailSerializer`
    - Sobreescribir `perform_create(serializer)`:
      - Obtener el boliche del `validated_data`
      - Si `boliche.dueno != request.user` → `raise PermissionDenied`
      - Llamar `serializer.save()`
  - _Requisitos: 5.1–5.5_

  - [ ]* 7.1 Tests de creación
    - `test_crear_evento_como_dueno`: POST → 201, respuesta incluye `precio_publicado` y `desglose_precio`
    - `test_crear_evento_boliche_ajeno_devuelve_403`
    - `test_crear_evento_sin_auth_devuelve_401`
    - `test_crear_evento_precio_base_negativo_devuelve_400`
    - `test_crear_evento_aforo_cero_devuelve_400`
    - `test_crear_evento_campos_faltantes_devuelve_400`
    - _Requisitos: 5.1–5.5_

- [ ] 8. Vista `PATCH /api/eventos/:id/` — Editar evento
  - Integrar en `EventoDetailView`:
    - Sobreescribir `update(request, *args, **kwargs)`:
      1. Verificar `IsDueno` → si no, 403
      2. Obtener el evento; si `estado == 'cancelado'` → 405 con `{"error": "No se puede editar un evento cancelado"}`
      3. Verificar que `evento.boliche.dueno == request.user` → si no, 403
      4. Continuar con la actualización parcial (`partial=True`)
  - _Requisitos: 6.1–6.5_

  - [ ]* 8.1 Tests de edición
    - `test_patch_evento_activo_exitoso`: editar nombre → 200, campo actualizado
    - `test_patch_evento_cancelado_devuelve_405`
    - `test_patch_evento_de_otro_dueno_devuelve_403`
    - `test_patch_sin_auth_devuelve_401`
    - `test_patch_datos_invalidos_devuelve_400`
    - _Requisitos: 6.1–6.5_

- [ ] 9. Vista `POST /api/eventos/:id/cancelar/` — Cancelar evento
  - `EventoCancelarView(APIView)`:
    - `permission_classes = [IsDueno]`
    - Método `post(self, request, pk)`:
      1. Obtener evento; si no existe → 404
      2. Si `evento.estado == 'cancelado'` → 409 `{"error": "El evento ya está cancelado"}`
      3. Si `evento.boliche.dueno != request.user` → 403
      4. Validar `motivo = request.data.get('motivo', '').strip()` → si vacío → 400
      5. `evento.estado = 'cancelado'`, `evento.motivo_cancelacion = motivo`, `evento.save()`
      6. Llamar `_intentar_reembolso(evento.id)` (importación dinámica con try/except ImportError)
      7. Devolver 200: `{id, estado, motivo_cancelacion, reembolsos_iniciados}`
  - Función privada `_intentar_reembolso(evento_id)` en el mismo archivo:
    ```python
    def _intentar_reembolso(evento_id):
        try:
            from apps.pagos.services import reembolsar_evento
            return reembolsar_evento(evento_id)
        except ImportError:
            import logging
            logging.getLogger(__name__).warning(
                "apps.pagos no disponible. Reembolsos no procesados para evento %s", evento_id
            )
            return 0
    ```
  - _Requisitos: 7.1–7.7_

  - [ ]* 9.1 Tests de cancelación
    - `test_cancelar_evento_exitoso`: estado cambia, motivo guardado, respuesta correcta
    - `test_cancelar_sin_motivo_devuelve_400`
    - `test_cancelar_motivo_solo_espacios_devuelve_400`
    - `test_cancelar_evento_ya_cancelado_devuelve_409`
    - `test_cancelar_evento_de_otro_dueno_devuelve_403`
    - `test_cancelar_evento_inexistente_devuelve_404`
    - `test_cancelar_sin_pagos_disponibles_devuelve_cero_reembolsos`: mockear ImportError en pagos
    - `test_patch_evento_cancelado_despues_de_cancelar_devuelve_405`
    - _Requisitos: 7.1–7.7_

- [ ] 10. Vista `GET /api/precios/calcular/` — Calculadora de precios
  - `CalcularPrecioView(APIView)`:
    - `permission_classes = [AllowAny]`
    - Método `get(self, request)`:
      1. `precio_base = request.query_params.get('precio_base')` → si None → 400
      2. Llamar `calcular_precio_publicado(precio_base)` en try/except `ValueError` → si ValueError → 400
      3. Devolver 200 con el resultado
  - _Requisitos: 9.1–9.4_

  - [ ]* 10.1 Tests de calculadora
    - `test_calcular_precio_endpoint_exitoso`: ?precio_base=5000 → 200 con desglose
    - `test_calcular_precio_sin_param_devuelve_400`
    - `test_calcular_precio_no_numerico_devuelve_400`
    - `test_calcular_precio_cero_devuelve_400`
    - `test_calcular_precio_sin_auth_permitido`: sin token → 200 (es público)
    - _Requisitos: 9.1–9.4_

- [ ] 11. URLs y registro en el router principal
  - Crear `apps/eventos/urls.py`:
    ```python
    from django.urls import path
    from .views import EventoListView, EventoCreateView, EventoDetailView, EventoCancelarView, CalcularPrecioView

    evento_urlpatterns = [
        path('',                   EventoListView.as_view(),    name='evento-list'),
        path('crear/',             EventoCreateView.as_view(),  name='evento-create'),
        path('<int:pk>/',          EventoDetailView.as_view(),  name='evento-detail'),
        path('<int:pk>/cancelar/', EventoCancelarView.as_view(), name='evento-cancelar'),
    ]

    precio_urlpatterns = [
        path('calcular/', CalcularPrecioView.as_view(), name='precio-calcular'),
    ]
    ```
  - En `config/urls.py` agregar:
    ```python
    from apps.eventos.urls import evento_urlpatterns, precio_urlpatterns
    path('api/eventos/', include(evento_urlpatterns)),
    path('api/precios/', include(precio_urlpatterns)),
    ```
  - _Requisito: 10.2_

- [ ] 12. Checkpoint final
  - `python manage.py check` — sin errores
  - `python manage.py test apps.eventos` — todos los tests pasan
  - Crear un evento de prueba desde el admin con un `precio_base` de $5000
  - Verificar `GET /api/eventos/:id/` devuelve `desglose_precio` correcto
  - Verificar `GET /api/precios/calcular/?precio_base=5000` devuelve el mismo desglose
  - Cancelar el evento vía `POST /api/eventos/:id/cancelar/` y verificar que PATCH posterior devuelve 405

---

## Notas

- Las subtareas marcadas con `*` son opcionales y se pueden completar después del MVP
- El acoplamiento con `apps.pagos` es intencional y débil — la vista de cancelación nunca falla por ausencia de `apps.pagos`
- Una vez que `apps.pagos` implemente `reembolsar_evento`, el import dinámico la encontrará automáticamente sin cambios en esta app
