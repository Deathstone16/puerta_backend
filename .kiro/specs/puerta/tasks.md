# Plan de implementación — App `puerta`

## Resumen

Implementación incremental de la app `puerta`: modelo `Asistente`, mixin `EventoActivoMixin`, endpoints de lista pública, guardia, cajera y aforo. Esta app es la más crítica del MVP — sin ella no hay operación de puerta.

**Prerequisitos:**
- `apps.cuentas` con permisos `IsGuardia`, `IsCajera`, `IsDueno`
- `apps.eventos` migrada con modelo `Evento`
- `apps.rrpp` migrada con modelo `LinkRRPP`

---

## Tareas

- [ ] 1. Crear la app y el modelo `Asistente`
  - Ejecutar `python manage.py startapp puerta` dentro de `api/apps/`
  - Crear `apps/puerta/models.py` con el modelo `Asistente` según el diseño
  - Todos los campos tal como están especificados, incluyendo `unique_together = ('evento', 'dni')`
  - Agregar `'apps.puerta'` a `INSTALLED_APPS` en `config/settings.py`
  - Ejecutar `python manage.py makemigrations puerta` y `python manage.py migrate`
  - _Requisitos: 1.1, 1.2, 1.3_

  - [ ]* 1.1 Tests del modelo
    - Crear `apps/puerta/tests.py`
    - `test_wallet_token_generado_automaticamente`: crear Asistente, verificar que `wallet_token` es UUID
    - `test_unique_together_dni_evento`: crear dos asistentes con el mismo DNI en el mismo evento → IntegrityError
    - `test_mismo_dni_diferente_evento_permitido`: mismo DNI en dos eventos distintos → OK
    - _Requisitos: 1.1, 1.2_

- [ ] 2. Admin de Django para `Asistente`
  - Editar `apps/puerta/admin.py`
  - `@admin.register(Asistente)` con `AsistenteAdmin(ModelAdmin)`:
    - `list_display = ['nombre', 'apellido', 'dni', 'evento', 'tipo_ingreso', 'estado', 'metodo_pago', 'created_at']`
    - `list_filter = ['estado', 'tipo_ingreso', 'metodo_pago', 'evento']`
    - `search_fields = ['nombre', 'apellido', 'dni']`
    - `readonly_fields = ['wallet_token', 'mp_payment_id', 'created_at', 'aprobado_at', 'ingresado_at', 'rebotado_at']`
  - Cargar algunos asistentes de prueba desde el admin para facilitar testing manual
  - _Requisito: 1.4_

- [ ] 3. Mixin `EventoActivoMixin`
  - Crear `apps/puerta/mixins.py`
  - Implementar `EventoActivoMixin` con método `verificar_evento_activo(self, evento)`:
    - Si `evento.estado == 'cancelado'` → devolver `Response({'error': 'SISTEMA BLOQUEADO - EVENTO CANCELADO', 'motivo': evento.motivo_cancelacion or ''}, status=423)`
    - Si evento activo → devolver `None`
  - _Requisito: 2.1, 2.2, 2.3_

  - [ ]* 3.1 Test del mixin
    - `test_evento_cancelado_devuelve_423`: llamar a `verificar_evento_activo` con evento cancelado, verificar Response 423
    - `test_evento_activo_devuelve_none`: verificar que retorna None con evento activo
    - _Requisito: 2.2_

- [ ] 4. Endpoints públicos — Lista RRPP
  - Crear `apps/puerta/views.py`
  - `ListaInfoView(APIView)` — `GET /api/lista/:slug/`:
    - `permission_classes = [AllowAny]`
    - `get_object_or_404(LinkRRPP, slug=slug, tipo='lista')`
    - Si `not link.activo` → 410
    - Contar `Asistente.objects.filter(link_rrpp=link).count()`
    - Devolver: `{evento: {id, nombre, fecha, boliche_nombre, color_pulsera}, rrpp_nombre, link_activo, anotados}`
  - `ListaAnotarView(EventoActivoMixin, APIView)` — `POST /api/lista/:slug/anotar/`:
    - `permission_classes = [AllowAny]`
    - Validar link activo → 410
    - `verificar_evento_activo` → 423
    - Validar campos `nombre`, `apellido`, `dni` → 400
    - Verificar `Asistente.objects.filter(evento=link.asignacion.evento, dni=dni).exists()` → 409
    - Crear Asistente con `tipo_ingreso='lista_rrpp'`, `estado='pendiente'`, `link_rrpp=link`
    - Devolver 201
  - _Requisitos: 3.1–3.4, 4.1–4.5_

  - [ ]* 4.1 Tests de lista pública
    - `test_get_info_lista_exitoso`
    - `test_get_info_lista_slug_inexistente_devuelve_404`
    - `test_get_info_lista_inactiva_devuelve_410`
    - `test_anotar_exitoso`
    - `test_anotar_dni_duplicado_devuelve_409`
    - `test_anotar_link_inactivo_devuelve_410`
    - `test_anotar_campos_faltantes_devuelve_400`
    - `test_anotar_evento_cancelado_devuelve_423`
    - _Requisitos: 3.1–3.4, 4.1–4.5_

- [ ] 5. Endpoints de Guardia
  - `GuardiaEscanearView(EventoActivoMixin, APIView)` — `POST /api/puerta/guardia/escanear/`:
    - `permission_classes = [IsGuardia]`
    - Si `'qr_code'` en body → buscar por `wallet_token=qr_code`
    - Si `'dni'` + `'evento_id'` en body → buscar por ambos campos
    - Si no encuentra → 404 `{"error": "No encontrado en la lista de este evento"}`
    - `verificar_evento_activo(asistente.evento)` → 423
    - Devolver datos del asistente
  - `GuardiaAprobarView(EventoActivoMixin, APIView)` — `POST /api/puerta/guardia/aprobar/:id/`:
    - `permission_classes = [IsGuardia]`
    - `verificar_evento_activo` → 423
    - Si `asistente.estado != 'pendiente'` → 400
    - Cambiar estado, guardar `aprobado_at = now()`
    - `save(update_fields=['estado', 'aprobado_at'])`
    - Devolver 200
  - `GuardiaRebotarView(EventoActivoMixin, APIView)` — `POST /api/puerta/guardia/rebotar/:id/`:
    - `permission_classes = [IsGuardia]`
    - `verificar_evento_activo` → 423
    - Si `asistente.estado != 'pendiente'` → 400
    - Validar `motivo` no vacío → 400
    - Cambiar estado, guardar `rebotado_at = now()`, `motivo_rechazo = motivo`
    - `save(update_fields=['estado', 'rebotado_at', 'motivo_rechazo'])`
  - _Requisitos: 5.1–5.7_

  - [ ]* 5.1 Tests de guardia
    - `test_escanear_por_qr_exitoso`
    - `test_escanear_por_dni_exitoso`
    - `test_escanear_no_encontrado_devuelve_404`
    - `test_aprobar_pendiente_exitoso`
    - `test_aprobar_no_pendiente_devuelve_400`
    - `test_rebotar_con_motivo_exitoso`
    - `test_rebotar_sin_motivo_devuelve_400`
    - `test_rebotar_no_pendiente_devuelve_400`
    - `test_guardia_evento_cancelado_devuelve_423`
    - _Requisitos: 5.1–5.7_

- [ ] 6. Endpoints de Cajera — Flujos web y lista
  - `CajeraEscanearWebView(EventoActivoMixin, APIView)` — `POST /api/puerta/cajera/escanear-web/:id/`:
    - `permission_classes = [IsCajera]`
    - `verificar_evento_activo` → 423
    - Si `asistente.tipo_ingreso != 'web_anticipada'` → 400 `{"error": "Este asistente no es de compra web"}`
    - Si `asistente.estado != 'aprobado_guardia'` → 409 con `estado_actual`
    - Cambiar a `ingresado_final`, `metodo_pago='ya_pago_web'`, `ingresado_at=now()`
    - Devolver 200 con `color_pulsera` y mensaje
  - `CajeraCobrarListaView(EventoActivoMixin, APIView)` — `POST /api/puerta/cajera/cobrar-lista/:id/`:
    - `permission_classes = [IsCajera]`
    - `verificar_evento_activo` → 423
    - Si `asistente.estado != 'aprobado_guardia'` → 409
    - Validar `metodo_pago` y `monto_pagado` del body → 400 si inválidos
    - Cambiar a `ingresado_final`, guardar pago, `ingresado_at=now()`
    - Devolver 200 con `color_pulsera` y mensaje
  - _Requisitos: 6.1, 6.2, 6.4, 6.6, 6.7_

  - [ ]* 6.1 Tests cajera flujos web y lista
    - `test_escanear_web_exitoso`
    - `test_escanear_web_sin_guardia_devuelve_409`
    - `test_escanear_web_tipo_incorrecto_devuelve_400`
    - `test_cobrar_lista_exitoso_efectivo`
    - `test_cobrar_lista_exitoso_transferencia`
    - `test_cobrar_lista_sin_guardia_devuelve_409`
    - `test_cajera_evento_cancelado_devuelve_423`
    - _Requisitos: 6.1, 6.2, 6.4_

- [ ] 7. Endpoint de Cajera — Venta general
  - `CajeraVentaGeneralView(EventoActivoMixin, APIView)` — `POST /api/puerta/cajera/venta-general/`:
    - `permission_classes = [IsCajera]`
    - Obtener `evento = get_object_or_404(Evento, pk=evento_id)`
    - `verificar_evento_activo(evento)` → 423
    - Extraer lista `personas` del body → 400 si vacía o faltante
    - Verificar duplicados de DNI dentro de la lista enviada → 400
    - Verificar que ningún DNI ya existe en el evento → 409 con lista de DNIs conflictivos
    - Crear todos los asistentes con `bulk_create`:
      ```python
      Asistente.objects.bulk_create([
          Asistente(evento=evento, nombre=p['nombre'], apellido=p.get('apellido',''),
                    dni=p['dni'], tipo_ingreso='venta_general',
                    estado='ingresado_final', metodo_pago=p['metodo_pago'],
                    monto_pagado=evento.precio_publicado, ingresado_at=now())
          for p in personas
      ])
      ```
    - Devolver 201 con lista de asistentes creados y `color_pulsera`
  - _Requisitos: 6.3, 6.5, 6.6, 6.7_

  - [ ]* 7.1 Tests de venta general
    - `test_venta_general_crea_n_asistentes_ingresados`
    - `test_venta_general_dni_duplicado_en_evento_devuelve_409`
    - `test_venta_general_dni_duplicado_en_request_devuelve_400`
    - `test_venta_general_respuesta_incluye_color_pulsera`
    - _Requisitos: 6.3, 6.5_

- [ ] 8. Endpoint de Cajera — Deshacer ingreso
  - `CajeraDeshacerView(APIView)` — `POST /api/puerta/cajera/deshacer/:id/`:
    - `permission_classes = [IsCajera]`
    - Si `asistente.estado != 'ingresado_final'` → 400
    - Calcular `delta = now() - asistente.ingresado_at`
    - Si `delta.total_seconds() > 600` (10 minutos) → 403
    - Revertir: `estado='aprobado_guardia'`, `ingresado_at=None`, `metodo_pago=None`, `monto_pagado=None`
    - `save(update_fields=['estado', 'ingresado_at', 'metodo_pago', 'monto_pagado'])`
    - Devolver 200
  - _Requisitos: 7.1–7.4_

  - [ ]* 8.1 Tests de deshacer
    - `test_deshacer_dentro_ventana_exitoso`: `ingresado_at` hace 5 minutos → OK
    - `test_deshacer_fuera_ventana_devuelve_403`: `ingresado_at` hace 15 minutos → 403
    - `test_deshacer_no_ingresado_devuelve_400`
    - `test_deshacer_limpia_campos_de_pago`: verificar que metodo_pago y monto_pagado quedan None
    - _Requisitos: 7.1–7.4_

- [ ] 9. Endpoint de aforo en vivo
  - `AforoView(APIView)` — `GET /api/dashboard/aforo/:evento_id/`:
    - Si DRF >= 3.9: `permission_classes = [IsGuardia | IsCajera | IsDueno]`
    - Si no soporta `|`: crear permiso custom `IsStaff` que verifique `rol in ['guardia', 'cajera', 'dueno']`
    - `evento = get_object_or_404(Evento, pk=evento_id)`
    - Calcular `ingresados`, `pendientes`, `porcentaje`
    - Devolver 200
  - _Requisitos: 8.1–8.6_

  - [ ]* 9.1 Tests de aforo
    - `test_aforo_calcula_ingresados_correctamente`
    - `test_aforo_calcula_pendientes`
    - `test_aforo_porcentaje_correcto`
    - `test_aforo_evento_inexistente_devuelve_404`
    - `test_aforo_accesible_por_guardia_cajera_dueno`
    - _Requisitos: 8.1–8.6_

- [ ] 10. URLs y registro en el router principal
  - Crear `apps/puerta/urls.py` con los cuatro grupos de URL patterns según el diseño
  - En `config/urls.py` agregar:
    ```python
    from apps.puerta.urls import lista_urlpatterns, guardia_urlpatterns, cajera_urlpatterns, dashboard_urlpatterns

    path('api/lista/',          include(lista_urlpatterns)),
    path('api/puerta/guardia/', include(guardia_urlpatterns)),
    path('api/puerta/cajera/',  include(cajera_urlpatterns)),
    path('api/dashboard/',      include(dashboard_urlpatterns)),
    ```
  - _Requisito: 9.1–9.5_

- [ ] 11. Checkpoint final — Flujo completo end-to-end
  - `python manage.py check` — sin errores
  - `python manage.py test apps.puerta` — todos los tests pasan
  - Simular noche completa con Postman:
    1. Login como `juan_rrpp` → anotar 3 personas en lista
    2. Login como `maria_guardia` → escanear por DNI → aprobar 2, rebotar 1
    3. Login como `ana_cajera` → cobrar lista para los 2 aprobados → aforo = 2
    4. Cajera → venta general con 3 personas nuevas → aforo = 5
    5. `GET /api/dashboard/aforo/:id/` → `{ingresados: 5, ...}`
    6. Intentar procesar al rebotado desde cajera → 409
    7. Deshacer uno de los ingresos → aforo = 4

---

## Notas

- Las subtareas con `*` son opcionales para el MVP
- `update_fields` en cada `save()` es importante para performance — solo actualiza los campos que cambiaron
- `bulk_create` en venta general no dispara signals, lo cual es correcto — no hay nada que notificar
- Si DRF no soporta `|` en permisos, el permiso custom `IsStaff` es 5 líneas y más legible
