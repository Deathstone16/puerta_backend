# Documento de Requisitos — App `pagos`

## Introducción

La app `pagos` gestiona la integración con Mercado Pago: creación de preferencias de pago, recepción del webhook de pago aprobado, consulta pública del wallet del comprador y reembolsos automáticos al cancelar un evento.

El modelo de negocio es Marketplace simple: el cliente paga el `precio_publicado`, Mercado Pago descuenta su comisión, Norware retiene un `application_fee` calculado sobre el `precio_base`, y el dueño recibe el neto en su cuenta (`collector_id_mp`). Todo en una sola transacción sin OAuth.

Esta app no tiene modelos propios — crea y consulta instancias de `Asistente` de `apps.puerta`.

## Glosario

- **Sistema**: La app `pagos` del backend Norware.
- **Preferencia MP**: Objeto de Mercado Pago que define los items, montos, comisiones y URLs de retorno de una sesión de pago. Se crea via API de MP y devuelve un `init_point` (URL de checkout).
- **init_point**: URL de la página de pago de Mercado Pago a la que se redirige al comprador.
- **application_fee**: Monto en ARS que Norware retiene de cada transacción. Se calcula como `precio_base × NORWARE_FEE_PCT / 100`.
- **collector_id**: ID de la cuenta de Mercado Pago del dueño del boliche. Se almacena en `Boliche.collector_id_mp`.
- **webhook**: Notificación HTTP POST que MP envía al backend cuando un pago es aprobado.
- **wallet_token**: UUID único del Asistente, usado como identificador público del ticket en la URL `/wallet/:token`.
- **reembolsar_evento**: Función en `apps/pagos/services.py` que itera los asistentes con compra web de un evento y solicita el reembolso a MP por cada uno.
- **Idempotencia**: Propiedad de una operación que produce el mismo resultado si se ejecuta múltiples veces. El webhook debe ser idempotente — si MP envía la misma notificación dos veces, no se crea un asistente duplicado.
- **mp_payment_id**: ID del pago en Mercado Pago. Usado como clave de idempotencia.

---

## Requisitos

### Requisito 1: Creación de preferencia de pago

**Historia de usuario:** Como potencial asistente, quiero poder iniciar el proceso de compra de una entrada anticipada y ser redirigido al checkout de Mercado Pago, para pagar de forma segura.

#### Criterios de aceptación

1. WHEN se realiza una petición `POST /api/pagos/preferencia/` con los campos `evento_id`, `nombre`, `apellido`, `dni` y `email` válidos, THE Sistema SHALL crear una preferencia de pago en Mercado Pago usando el SDK y devolver HTTP 200 con `{init_point, preference_id, precio_publicado, desglose}`.
2. THE Sistema SHALL incluir en la preferencia MP el campo `application_fee` calculado como `precio_base × NORWARE_FEE_PCT / 100`, redondeado a 2 decimales.
3. THE Sistema SHALL incluir en la preferencia MP el `collector_id` del dueño del boliche del evento, tomado de `Boliche.collector_id_mp`.
4. THE Sistema SHALL configurar en la preferencia MP los campos `back_urls` (success, failure, pending) apuntando al frontend (`FRONTEND_URL` desde settings) y `notification_url` apuntando a `POST /api/pagos/webhook/`.
5. WHEN ya existe un `Asistente` con el mismo DNI en el mismo evento, THE Sistema SHALL devolver HTTP 409 sin crear la preferencia.
6. WHEN el evento no existe o está cancelado, THE Sistema SHALL devolver HTTP 400.
7. WHEN la API de Mercado Pago devuelve un error al crear la preferencia, THE Sistema SHALL devolver HTTP 503 con un mensaje descriptivo.
8. THE Sistema SHALL permitir el acceso a `POST /api/pagos/preferencia/` sin autenticación.

---

### Requisito 2: Recepción del webhook de Mercado Pago

**Historia de usuario:** Como sistema, necesito procesar las notificaciones de pago aprobado que envía Mercado Pago, para crear el asistente con su ticket QR y enviarle el mail de confirmación.

#### Criterios de aceptación

1. WHEN el Sistema recibe una petición `POST /api/pagos/webhook/` con una notificación de tipo `payment` y estado `approved`, THE Sistema SHALL crear un `Asistente` con `tipo_ingreso='web_anticipada'`, `estado='aprobado_guardia'`, guardando el `mp_payment_id` y el `mp_fee_norware` real cobrado.
2. THE Sistema SHALL verificar la idempotencia antes de crear el Asistente: si ya existe un `Asistente` con el mismo `mp_payment_id`, THE Sistema SHALL devolver HTTP 200 sin crear ningún objeto adicional.
3. THE Sistema SHALL extraer del pago aprobado los datos del pagador (nombre, apellido, DNI o email) para asociarlos al Asistente. SI el DNI no está disponible en el pago MP, THE Sistema SHALL usar el email como identificador temporal y marcar el campo `dni` con el valor del email.
4. WHEN se crea el Asistente desde el webhook, THE Sistema SHALL enviar un mail al comprador con el link `/wallet/{wallet_token}` usando el backend SMTP configurado en settings.
5. THE Sistema SHALL responder HTTP 200 a todos los webhooks recibidos (incluyendo notificaciones de tipos distintos a `payment` o estados distintos a `approved`) para que MP no reintente el envío.
6. THE Sistema SHALL permitir el acceso a `POST /api/pagos/webhook/` sin autenticación (es un endpoint público de MP).

---

### Requisito 3: Wallet público del comprador

**Historia de usuario:** Como comprador de una entrada web, quiero poder acceder a mi ticket con QR desde el link que recibí por mail, para presentarlo en la puerta del evento.

#### Criterios de aceptación

1. WHEN se realiza una petición `GET /api/wallet/:token/` con un `wallet_token` existente, THE Sistema SHALL devolver HTTP 200 con los datos del Asistente (nombre, apellido, dni, estado, tipo_ingreso), los datos del evento (nombre, fecha, boliche, color_pulsera), el `qr_code` (el string del `wallet_token` que el guardia puede escanear) y un campo `evento_cancelado` boolean.
2. WHEN `evento_cancelado` es `True`, THE Sistema SHALL incluir `motivo_cancelacion` en la respuesta para que el frontend muestre el mensaje de devolución.
3. WHEN se realiza una petición `GET /api/wallet/:token/` con un token inexistente, THE Sistema SHALL devolver HTTP 404.
4. THE Sistema SHALL permitir el acceso a `GET /api/wallet/:token/` sin autenticación.

---

### Requisito 4: Reembolsos automáticos al cancelar evento

**Historia de usuario:** Como sistema, necesito poder iniciar los reembolsos de todas las compras web cuando un evento se cancela, para que los compradores recuperen su dinero automáticamente.

#### Criterios de aceptación

1. THE Sistema SHALL proveer una función `reembolsar_evento(evento_id)` en `apps/pagos/services.py` que itere todos los `Asistente` con `tipo_ingreso='web_anticipada'` del evento y solicite el reembolso a MP por cada uno.
2. THE Sistema SHALL usar una idempotency key única por transacción al solicitar reembolsos, con el formato `refund-{asistente.id}`, para evitar reembolsos duplicados si la función se llama más de una vez.
3. IF un reembolso individual falla (error de API de MP), THE Sistema SHALL registrar el error en el log, continuar con los demás reembolsos y no interrumpir el proceso completo.
4. THE Sistema SHALL devolver el número de reembolsos procesados exitosamente como entero.
5. IF el evento no tiene asistentes con `tipo_ingreso='web_anticipada'`, THE Sistema SHALL devolver 0 sin llamar a la API de MP.

---

### Requisito 5: Dashboard de recaudación

**Historia de usuario:** Como dueño de un boliche, quiero ver la recaudación de mi evento desglosada por método de pago, para auditar la caja de la noche.

#### Criterios de aceptación

1. WHEN un Dueño autenticado envía `GET /api/dashboard/recaudacion/:evento_id/`, THE Sistema SHALL devolver HTTP 200 con la recaudación agrupada por método de pago: `web` (suma de `monto_pagado` de asistentes `web_anticipada`), `efectivo` (suma de `monto_pagado` de asistentes con `metodo_pago='efectivo'`), `transferencia` (suma de `monto_pagado` de asistentes con `metodo_pago='transferencia'`), más `total_recaudado` y `comision_norware_web` (suma de `mp_fee_norware` de asistentes web).
2. THE Sistema SHALL incluir tanto el `monto` como la `cantidad` de asistentes por cada método de pago.
3. WHEN se consulta la recaudación de un evento que no pertenece al boliche del Dueño autenticado, THE Sistema SHALL devolver HTTP 403.
4. THE Sistema SHALL requerir autenticación con `IsDueno`.

---

### Requisito 6: Dashboard de métricas del superadmin

**Historia de usuario:** Como superadmin de Norware, quiero ver cuánto generó la plataforma en comisiones por cada evento, para auditar los ingresos de Norware.

#### Criterios de aceptación

1. WHEN un usuario con `rol=superadmin` envía `GET /api/admin/metricas/`, THE Sistema SHALL devolver HTTP 200 con un resumen por evento: `evento_id`, `evento_nombre`, `boliche`, `fecha`, `estado`, `entradas_web`, `comision_norware` (suma de `mp_fee_norware`) y `recaudado_total_web`; más los totales acumulados de Norware.
2. THE Sistema SHALL requerir autenticación con `IsSuperAdmin`.

---

### Requisito 7: Configuración de Mercado Pago y mail

**Historia de usuario:** Como desarrollador del equipo, quiero que la integración con MP y el envío de mails estén correctamente configurados en settings, para que funcionen en desarrollo con sandboxes y en producción con cuentas reales.

#### Criterios de aceptación

1. THE Sistema SHALL leer `MP_ACCESS_TOKEN` desde `.env` via `python-decouple` y configurarlo en `settings.py`.
2. THE Sistema SHALL leer `MP_COLLECTOR_ID` desde `.env` y usarlo como `collector_id` por defecto si el boliche no tiene uno configurado.
3. THE Sistema SHALL leer `FRONTEND_URL` desde `.env` para construir las `back_urls` de MP y los links en los mails.
4. THE Sistema SHALL configurar el backend de mail en `settings.py` con las variables `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` y `DEFAULT_FROM_EMAIL` leídas desde `.env`.
5. THE Sistema SHALL registrar `apps.pagos` en `INSTALLED_APPS` de `settings.py`.
6. THE Sistema SHALL incluir las URLs de la app `pagos` en `config/urls.py` bajo los prefijos `/api/pagos/`, `/api/wallet/` y `/api/dashboard/`.
