# Plan de implementación — App `pagos`

## Resumen

Implementación de la app `pagos`: wrapper del SDK de MP, vista de preferencia, webhook idempotente, wallet público, función de reembolsos y dashboards de recaudación. Esta app no tiene modelos propios — opera sobre `Asistente` de `apps.puerta`.

**Prerequisitos:**
- `apps.eventos` migrada con `Evento` y función `calcular_precio_publicado`
- `apps.boliches` migrada con `Boliche.collector_id_mp`
- `apps.puerta` migrada con modelo `Asistente`
- `apps.cuentas` con permisos `IsDueno`, `IsSuperAdmin`
- SDK de Mercado Pago instalado (`mercadopago` en `requirements.txt`)

---

## Tareas

- [ ] 1. Crear la app y configurar variables de entorno
  - Ejecutar `python manage.py startapp pagos` dentro de `api/apps/`
  - Agregar `'apps.pagos'` a `INSTALLED_APPS` en `config/settings.py`
  - Agregar en `config/settings.py`:
    ```python
    MP_ACCESS_TOKEN  = config('MP_ACCESS_TOKEN')
    MP_COLLECTOR_ID  = config('MP_COLLECTOR_ID', default='')
    FRONTEND_URL     = config('FRONTEND_URL', default='http://localhost:5173')
    BACKEND_URL      = config('BACKEND_URL',  default='http://localhost:8000')
    ```
  - Agregar configuración de mail en settings:
    ```python
    EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST          = config('EMAIL_HOST', default='smtp.sendgrid.net')
    EMAIL_PORT          = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_HOST_USER     = config('EMAIL_HOST_USER', default='')
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
    EMAIL_USE_TLS       = config('EMAIL_USE_TLS', default=True, cast=bool)
    DEFAULT_FROM_EMAIL  = config('DEFAULT_FROM_EMAIL', default='noreply@norware.com')
    ```
  - Actualizar `.env.example` con todas estas variables
  - _Requisitos: 7.1–7.5_

- [ ] 2. Wrapper del SDK de Mercado Pago
  - Crear `apps/pagos/mp_client.py`
  - Implementar `_get_sdk()` → devuelve `mercadopago.SDK(settings.MP_ACCESS_TOKEN)`
  - Implementar `crear_preferencia(evento, comprador: dict)`:
    - Calcular `precio_publicado` con `calcular_precio_publicado` de `apps.eventos.utils`
    - Calcular `application_fee` como `round(evento.precio_base × NORWARE_FEE_PCT / 100, 2)`
    - `collector_id` = `evento.boliche.collector_id_mp or settings.MP_COLLECTOR_ID`
    - Construir `preference_data` con `items`, `payer`, `application_fee`, `collector_id`, `back_urls`, `notification_url`, `external_reference`, `metadata`
    - Llamar `sdk.preference().create(preference_data)`
    - Si status no es 200/201 → `raise MPError`
    - Devolver `{init_point, preference_id}`
  - Implementar `obtener_pago(payment_id: str)` → llama `sdk.payment().get(payment_id)`, lanza MPError si falla
  - Implementar `reembolsar_pago(payment_id, idempotency_key)` → llama `sdk.payment().refunds(payment_id, headers)`, devuelve bool
  - Definir excepción `class MPError(Exception): pass`
  - _Requisitos: 1.1–1.4, 1.7_

  - [ ]* 2.1 Tests del mp_client (con mocks)
    - Crear `apps/pagos/tests.py`
    - `test_crear_preferencia_estructura_correcta`: mockear SDK, verificar campos de preference_data
    - `test_crear_preferencia_application_fee_correcto`: verificar aritmética
    - `test_crear_preferencia_mp_error_lanza_excepcion`: mock con status 400
    - _Requisitos: 1.2, 1.3, 1.7_

- [ ] 3. Vista `POST /api/pagos/preferencia/`
  - Crear `apps/pagos/views.py`
  - `PreferenciaView(APIView)`:
    - `permission_classes = [AllowAny]`
    - Método `post(self, request)`:
      1. Validar campos: `evento_id`, `nombre`, `apellido`, `dni`, `email` → 400 si faltan
      2. `evento = get_object_or_404(Evento, pk=evento_id)` → si `estado == 'cancelado'` → 400
      3. Verificar `Asistente.objects.filter(evento=evento, dni=dni).exists()` → 409
      4. Llamar `mp_client.crear_preferencia(evento, comprador)` en try/except MPError → 503
      5. Calcular `desglose` con `calcular_precio_publicado`
      6. Devolver 200 `{init_point, preference_id, precio_publicado, desglose}`
  - _Requisitos: 1.1–1.8_

  - [ ]* 3.1 Tests de preferencia
    - `test_preferencia_exitosa_devuelve_init_point`: mockear mp_client
    - `test_preferencia_evento_cancelado_devuelve_400`
    - `test_preferencia_dni_duplicado_devuelve_409`
    - `test_preferencia_campos_faltantes_devuelve_400`
    - `test_preferencia_mp_error_devuelve_503`: mockear MPError
    - _Requisitos: 1.1, 1.5, 1.6, 1.7, 1.8_

- [ ] 4. Vista `POST /api/pagos/webhook/`
  - `WebhookView(APIView)`:
    - `permission_classes = [AllowAny]`
    - Método `post(self, request)`:
      1. Extraer `type` (o `topic` de query params)
      2. Si `type != 'payment'` → devolver 200 `{'ok': True}` (ignorar)
      3. Extraer `payment_id` de `data.id` o query params
      4. Verificar idempotencia: `Asistente.objects.filter(mp_payment_id=payment_id).exists()` → si sí, 200
      5. Llamar `mp_client.obtener_pago(payment_id)` en try/except
      6. Si `pago['status'] != 'approved'` → 200 (ignorar)
      7. Extraer datos del comprador de `metadata` (evento_id, dni, nombre, apellido) con fallbacks a `payer`
      8. `fee_real = pago.get('fee_details', [{}])[0].get('amount', 0)`
      9. Crear `Asistente` con tipo_ingreso='web_anticipada', estado='aprobado_guardia', mp_payment_id, mp_fee_norware=fee_real
      10. Llamar `_enviar_mail_confirmacion(asistente)` (función privada en el mismo archivo)
      11. Devolver 200 (siempre, incluso si hay excepciones — wrap todo en try/except grande)
  - Función `_enviar_mail_confirmacion(asistente)`:
    - Construir `wallet_url = f"{settings.FRONTEND_URL}/wallet/{asistente.wallet_token}"`
    - `send_mail(subject, message, from_email, recipient_list, fail_silently=True)`
    - El email del comprador debe extraerse del pago MP — puede requerir agregar campo `email` al modelo `Asistente`
  - _Requisitos: 2.1–2.6_

  - [ ]* 4.1 Tests del webhook
    - `test_webhook_pago_aprobado_crea_asistente`: mockear obtener_pago con pago approved
    - `test_webhook_idempotente_no_duplica`: crear asistente con mp_payment_id, llamar webhook dos veces
    - `test_webhook_pago_no_approved_no_crea_asistente`: mock con status pending
    - `test_webhook_tipo_no_payment_ignorado`: topic='merchant_order' → 200, sin crear asistente
    - `test_webhook_siempre_responde_200`: incluso si hay exception interna
    - `test_webhook_envia_mail`: mockear send_mail, verificar que se llamó
    - _Requisitos: 2.1–2.6_

- [ ] 5. Vista `GET /api/wallet/:token/`
  - `WalletView(APIView)`:
    - `permission_classes = [AllowAny]`
    - Método `get(self, request, token)`:
      1. `asistente = get_object_or_404(Asistente, wallet_token=token)`
      2. Devolver datos del asistente + evento completo + `qr_code` (el string del wallet_token) + `evento_cancelado` bool + `motivo_cancelacion`
  - _Requisitos: 3.1–3.4_

  - [ ]* 5.1 Tests del wallet
    - `test_wallet_devuelve_datos_completos`
    - `test_wallet_token_inexistente_devuelve_404`
    - `test_wallet_evento_cancelado_incluye_motivo`
    - _Requisitos: 3.1–3.4_

- [ ] 6. Función `reembolsar_evento` en `services.py`
  - Crear `apps/pagos/services.py`
  - Implementar `reembolsar_evento(evento_id: int) -> int`:
    - `from apps.puerta.models import Asistente`
    - `asistentes_web = Asistente.objects.filter(evento_id=evento_id, tipo_ingreso='web_anticipada', mp_payment_id__isnull=False)`
    - Iterar cada asistente:
      ```python
      exitosos = 0
      for asistente in asistentes_web:
          try:
              ok = mp_client.reembolsar_pago(asistente.mp_payment_id, f"refund-{asistente.id}")
              if ok:
                  exitosos += 1
          except MPError as e:
              logger.error("...")
      return exitosos
      ```
  - _Requisitos: 4.1–4.5_

  - [ ]* 6.1 Tests de reembolsos
    - `test_reembolsar_evento_llama_mp_por_cada_asistente`: crear 3 asistentes web, mockear reembolsar_pago, verificar 3 llamadas
    - `test_reembolsar_evento_idempotency_key_correcta`: verificar formato "refund-{id}"
    - `test_reembolsar_evento_continua_si_uno_falla`: mock con una llamada lanzando MPError → verifica que las otras 2 se procesan
    - `test_reembolsar_evento_sin_asistentes_web_devuelve_cero`
    - _Requisitos: 4.1–4.5_

- [ ] 7. Vista `GET /api/dashboard/recaudacion/:evento_id/`
  - `RecaudacionView(APIView)`:
    - `permission_classes = [IsDueno]`
    - Método `get(self, request, evento_id)`:
      1. `evento = get_object_or_404(Evento, pk=evento_id)`
      2. Si `evento.boliche.dueno != request.user` → 403
      3. `qs = Asistente.objects.filter(evento=evento, estado='ingresado_final')`
      4. Calcular agregados con `.aggregate(Sum, Count)` para cada método de pago
      5. Devolver desglose completo
  - _Requisitos: 5.1–5.4_

  - [ ]* 7.1 Tests de recaudación
    - `test_recaudacion_desglose_correcto`: crear asistentes con distintos métodos, verificar sumas
    - `test_recaudacion_evento_ajeno_devuelve_403`
    - `test_recaudacion_sin_auth_devuelve_401`
    - _Requisitos: 5.1–5.4_

- [ ] 8. Vista `GET /api/admin/metricas/`
  - `MetricasAdminView(APIView)`:
    - `permission_classes = [IsSuperAdmin]`
    - Devolver todos los eventos con sus comisiones Norware + totales acumulados
  - _Requisito: 6.1, 6.2_

  - [ ]* 8.1 Tests de métricas admin
    - `test_metricas_accesible_por_superadmin`
    - `test_metricas_rechaza_dueno`: rol incorrecto → 403
    - _Requisito: 6.2_

- [ ] 9. URLs y registro en el router principal
  - Crear `apps/pagos/urls.py` con 4 grupos de URL patterns según el diseño
  - En `config/urls.py` agregar:
    ```python
    from apps.pagos.urls import pagos_urlpatterns, wallet_urlpatterns, dashboard_pagos_urlpatterns, admin_urlpatterns

    path('api/pagos/',     include(pagos_urlpatterns)),
    path('api/wallet/',    include(wallet_urlpatterns)),
    path('api/dashboard/', include(dashboard_pagos_urlpatterns)),  # se suma a los de puerta
    path('api/admin/',     include(admin_urlpatterns)),
    ```
  - _Requisito: 7.6_

- [ ] 10. Checkpoint final — Flujo de compra end-to-end
  - `python manage.py check` — sin errores
  - `python manage.py test apps.pagos` — todos los tests pasan (con mocks de MP)
  - Simular compra web en sandbox:
    1. Crear evento con precio_base=5000 desde el admin
    2. `POST /api/pagos/preferencia/` → obtener `init_point`
    3. Abrir `init_point` en el navegador → checkout sandbox de MP
    4. Pagar con tarjeta de prueba de MP
    5. Verificar que llega el webhook → asistente creado en `aprobado_guardia`
    6. `GET /api/wallet/:token/` → ver ticket con QR
    7. Simular cancelación del evento desde `POST /api/eventos/:id/cancelar/` → verificar que `reembolsar_evento` se llama (puede mockearse en esta fase)
  - **Importante:** en desarrollo local, MP no puede enviar webhooks a `localhost`. Usar ngrok o similar para exponer el backend temporalmente, o testear el webhook manualmente con Postman replicando el payload de MP.

---

## Notas

- Subtareas con `*` opcionales para MVP
- **Mocks obligatorios:** NUNCA llamar a la API real de MP en tests — siempre mockear `_get_sdk()` o las funciones de `mp_client`
- El campo `email` en `Asistente` puede ser necesario — evaluar agregarlo al modelo en `apps.puerta` antes de implementar esta app
- El webhook SIEMPRE debe responder 200, incluso si hay errores internos — si no, MP reintenta indefinidamente
- `fail_silently=True` en `send_mail` es crítico — un error de SMTP no debe romper el webhook
