# Documento de Requisitos — App `puerta`

## Introducción

La app `puerta` implementa el flujo operativo de la noche del evento: control de acceso en dos puntos (guardia y cajera) y consulta de aforo en vivo. El modelo central es `Asistente`, que almacena a cada persona que concurrirá o concurrió al evento, con un estado que evoluciona a medida que atraviesa los dos controles de puerta.

El flujo estándar es: guardia escanea o busca por DNI → aprueba o rebota → cajera cobra (si aplica) → ingreso final. La compra web anticipada nace directamente en `aprobado_guardia` y solo necesita un segundo escaneo en cajera para ingresar.

## Glosario

- **Sistema**: La app `puerta` del backend Norware (Django + DRF).
- **Asistente**: Persona registrada para concurrir a un evento. Puede ser de tres tipos: `web_anticipada`, `lista_rrpp`, `venta_general`.
- **Guardia**: Usuario con `rol=guardia`. Primer control en puerta — aprueba o rebota.
- **Cajera**: Usuario con `rol=cajera`. Segundo control — cobra (si aplica) y da ingreso final.
- **Dueño**: Usuario con `rol=dueno`. Consulta aforo y métricas del evento.
- **Estado del Asistente**: `pendiente`, `aprobado_guardia`, `rebotado_guardia`, `ingresado_final`.
- **wallet_token**: UUID único asociado a cada Asistente, usado como identificador público en el QR del ticket.
- **Doble control**: Regla crítica — la cajera solo procesa asistentes en `aprobado_guardia`. Si el estado es otro → error 409.
- **Rebotado**: Estado terminal — una vez rebotado, el asistente no puede avanzar a ningún otro estado.
- **Deshacer**: Operación de la cajera que revierte un `ingresado_final` a `aprobado_guardia` dentro de los 10 minutos de `ingresado_at`.
- **EventoActivoMixin**: Mixin reutilizable que bloquea todos los endpoints de puerta si el evento está cancelado (HTTP 423).
- **Aforo**: Cantidad de asistentes en estado `ingresado_final` para un evento.

---

## Requisitos

### Requisito 1: Modelo `Asistente` con estados y timestamps

**Historia de usuario:** Como sistema, necesito un modelo `Asistente` con campos de identificación, tipo de ingreso, estado, método de pago, montos y timestamps, para rastrear el ciclo completo de cada persona desde que se anota hasta que ingresa al boliche.

#### Criterios de aceptación

1. THE Sistema SHALL definir el modelo `Asistente` con los campos: `evento` (FK a `eventos.Evento`, `on_delete=PROTECT`), `link_rrpp` (FK nullable a `rrpp.LinkRRPP`, `on_delete=SET_NULL`), `nombre` (CharField, max 100), `apellido` (CharField, max 100), `dni` (CharField, max 20), `tipo_ingreso` (CharField, choices: `web_anticipada`/`lista_rrpp`/`venta_general`), `estado` (CharField, choices: `pendiente`/`aprobado_guardia`/`rebotado_guardia`/`ingresado_final`, default `pendiente`), `metodo_pago` (CharField nullable, choices: `efectivo`/`transferencia`/`ya_pago_web`), `monto_pagado` (DecimalField nullable), `wallet_token` (UUIDField, default `uuid4`, unique, editable=False), `mp_payment_id` (CharField nullable, unique), `mp_fee_norware` (DecimalField nullable), `motivo_rechazo` (TextField nullable), `created_at` (DateTimeField, auto_now_add), `aprobado_at` (DateTimeField nullable), `ingresado_at` (DateTimeField nullable), `rebotado_at` (DateTimeField nullable).
2. THE Sistema SHALL definir `unique_together = ('evento', 'dni')` en el Meta del modelo `Asistente`.
3. THE Sistema SHALL generar y aplicar migraciones para el modelo `Asistente`.
4. THE Sistema SHALL registrar el modelo `Asistente` en el admin de Django con filtros por `estado` y `evento`.

---

### Requisito 2: Mixin `EventoActivoMixin` — bloqueo de operaciones sobre evento cancelado

**Historia de usuario:** Como sistema, necesito que todos los endpoints de puerta (guardia y cajera) validen que el evento está activo antes de ejecutar cualquier operación, para evitar que se procesen asistentes de eventos cancelados.

#### Criterios de aceptación

1. THE Sistema SHALL proveer un mixin `EventoActivoMixin` en `apps/puerta/mixins.py` que implemente una validación común reutilizable por todas las vistas de puerta.
2. WHEN una vista que usa `EventoActivoMixin` recibe una petición que involucra un evento con `estado='cancelado'`, THE Sistema SHALL responder con HTTP 423 y el cuerpo `{"error": "SISTEMA BLOQUEADO - EVENTO CANCELADO", "motivo": "..."}`.
3. THE Sistema SHALL aplicar esta validación antes de cualquier otra lógica de negocio en los endpoints de guardia y cajera.

---

### Requisito 3: Endpoint público — Información del link de lista

**Historia de usuario:** Como potencial asistente, quiero ver los datos del evento cuando accedo al link de lista de un RRPP, para saber a qué evento me estoy anotando.

#### Criterios de aceptación

1. WHEN se realiza una petición `GET /api/lista/:slug/`, THE Sistema SHALL devolver HTTP 200 con los datos del evento asociado al link (nombre, fecha, boliche, color_pulsera), el nombre del RRPP, el estado del link (`activo` boolean) y la cantidad de anotados actuales.
2. WHEN se realiza una petición `GET /api/lista/:slug/` con un slug inexistente, THE Sistema SHALL devolver HTTP 404.
3. WHEN el link tiene `activo=False`, THE Sistema SHALL devolver HTTP 410.
4. THE Sistema SHALL permitir el acceso a `GET /api/lista/:slug/` sin autenticación.

---

### Requisito 4: Endpoint público — Anotación en lista RRPP

**Historia de usuario:** Como potencial asistente, quiero anotarme en la lista de un RRPP enviando mi nombre, apellido y DNI, para poder ingresar al evento pagando en puerta.

#### Criterios de aceptación

1. WHEN se realiza una petición `POST /api/lista/:slug/anotar/` con los campos `nombre`, `apellido` y `dni` válidos, THE Sistema SHALL crear un `Asistente` con `tipo_ingreso='lista_rrpp'` y `estado='pendiente'` asociado al link, y devolver HTTP 201 con los datos del asistente creado.
2. WHEN ya existe un `Asistente` con el mismo DNI en el mismo evento, THE Sistema SHALL devolver HTTP 409.
3. WHEN el link tiene `activo=False`, THE Sistema SHALL devolver HTTP 410.
4. WHEN falta alguno de los campos requeridos (`nombre`, `apellido`, `dni`), THE Sistema SHALL devolver HTTP 400 con un mensaje descriptivo.
5. THE Sistema SHALL permitir el acceso a `POST /api/lista/:slug/anotar/` sin autenticación.

---

### Requisito 5: Endpoints de guardia — Escanear, aprobar y rebotar

**Historia de usuario:** Como guardia, quiero poder buscar un asistente por QR o DNI, aprobarlo para que pase a caja o rebotarlo si no cumple los requisitos de admisión, para controlar el acceso al boliche.

#### Criterios de aceptación

1. WHEN un Guardia autenticado envía `POST /api/puerta/guardia/escanear/` con `{qr_code}` o `{dni, evento_id}`, THE Sistema SHALL buscar el `Asistente` correspondiente y devolver HTTP 200 con sus datos completos (nombre, dni, tipo_ingreso, estado, rrpp_nombre si aplica).
2. WHEN un Guardia autenticado envía `POST /api/puerta/guardia/aprobar/:id/` sobre un Asistente en estado `pendiente`, THE Sistema SHALL cambiar el estado a `aprobado_guardia`, guardar `aprobado_at` con el timestamp actual y devolver HTTP 200 con el mensaje "Aprobado. Pasa a caja.".
3. WHEN un Guardia autenticado envía `POST /api/puerta/guardia/rebotar/:id/` con un campo `motivo` sobre un Asistente en estado `pendiente`, THE Sistema SHALL cambiar el estado a `rebotado_guardia`, guardar `rebotado_at` y `motivo_rechazo`, y devolver HTTP 200.
4. WHEN se intenta aprobar o rebotar un Asistente que no está en estado `pendiente`, THE Sistema SHALL devolver HTTP 400.
5. WHEN no se encuentra ningún Asistente con el `qr_code` o `(dni, evento_id)` provisto, THE Sistema SHALL devolver HTTP 404 con el mensaje "No encontrado en la lista de este evento".
6. THE Sistema SHALL requerir autenticación con `IsGuardia` para todos los endpoints de guardia.
7. THE Sistema SHALL aplicar `EventoActivoMixin` a todas las vistas de guardia.

---

### Requisito 6: Endpoints de cajera — Tres flujos de ingreso

**Historia de usuario:** Como cajera, quiero poder procesar el ingreso de asistentes según tres flujos distintos (web anticipada, lista RRPP y venta general), para cobrar solo a quienes corresponda y dar ingreso final a todos.

#### Criterios de aceptación

1. WHEN una Cajera autenticada envía `POST /api/puerta/cajera/escanear-web/:id/` sobre un Asistente con `tipo_ingreso='web_anticipada'` y `estado='aprobado_guardia'`, THE Sistema SHALL cambiar el estado a `ingresado_final`, asignar `metodo_pago='ya_pago_web'`, guardar `ingresado_at` y devolver HTTP 200 con el `color_pulsera` del evento y el mensaje "Ingreso confirmado. Entregar pulsera {color}.".
2. WHEN una Cajera autenticada envía `POST /api/puerta/cajera/cobrar-lista/:id/` sobre un Asistente con `tipo_ingreso='lista_rrpp'` y `estado='aprobado_guardia'`, con los campos `{metodo_pago, monto_pagado}`, THE Sistema SHALL cambiar el estado a `ingresado_final`, guardar los datos de pago y devolver HTTP 200 con el `color_pulsera` y mensaje de confirmación.
3. WHEN una Cajera autenticada envía `POST /api/puerta/cajera/venta-general/` con `{evento_id, personas: [{nombre, apellido, dni, metodo_pago}]}`, THE Sistema SHALL crear N asistentes con `tipo_ingreso='venta_general'` y `estado='ingresado_final'` directamente (sin pasar por guardia) y devolver HTTP 201 con la lista de asistentes creados y el `color_pulsera`.
4. WHEN cualquier endpoint de cajera recibe un Asistente cuyo estado no es `aprobado_guardia` (salvo venta general que no consulta asistentes previos), THE Sistema SHALL devolver HTTP 409 con el mensaje "Falta validación del guardia" y el `estado_actual`.
5. WHEN en venta general algún DNI ya existe en el evento, THE Sistema SHALL devolver HTTP 409 indicando qué DNIs conflictúan.
6. THE Sistema SHALL requerir autenticación con `IsCajera` para todos los endpoints de cajera.
7. THE Sistema SHALL aplicar `EventoActivoMixin` a todas las vistas de cajera.

---

### Requisito 7: Endpoint de cajera — Deshacer ingreso

**Historia de usuario:** Como cajera, quiero poder revertir un ingreso que procesé por error, para corregir la situación sin intervención del administrador del sistema.

#### Criterios de aceptación

1. WHEN una Cajera autenticada envía `POST /api/puerta/cajera/deshacer/:id/` sobre un Asistente en estado `ingresado_final` cuyo `ingresado_at` fue hace menos de 10 minutos, THE Sistema SHALL cambiar el estado a `aprobado_guardia`, limpiar los campos `ingresado_at`, `metodo_pago` y `monto_pagado`, y devolver HTTP 200 con el mensaje "Ingreso revertido.".
2. WHEN `ingresado_at` fue hace más de 10 minutos, THE Sistema SHALL devolver HTTP 403 con el mensaje "No se puede deshacer: pasaron más de 10 minutos.".
3. WHEN el Asistente no está en estado `ingresado_final`, THE Sistema SHALL devolver HTTP 400.
4. THE Sistema SHALL requerir autenticación con `IsCajera`.

---

### Requisito 8: Endpoint de aforo en vivo

**Historia de usuario:** Como guardia, cajera o dueño, quiero consultar cuántas personas ya ingresaron al evento en tiempo real, para saber cuándo estamos cerca del aforo máximo.

#### Criterios de aceptación

1. WHEN un usuario autenticado con rol `guardia`, `cajera` o `dueno` envía `GET /api/dashboard/aforo/:evento_id/`, THE Sistema SHALL devolver HTTP 200 con `{evento_id, ingresados, aforo_max, porcentaje, pendientes}`.
2. THE Sistema SHALL calcular `ingresados` como la cantidad de Asistentes con `estado='ingresado_final'` en ese evento.
3. THE Sistema SHALL calcular `pendientes` como la cantidad de Asistentes con `estado` en `['pendiente', 'aprobado_guardia']`.
4. THE Sistema SHALL calcular `porcentaje` como `(ingresados / aforo_max) × 100` redondeado a 2 decimales.
5. WHEN se consulta el aforo de un evento inexistente, THE Sistema SHALL devolver HTTP 404.
6. THE Sistema SHALL permitir el acceso a `GET /api/dashboard/aforo/:evento_id/` a usuarios autenticados con `IsGuardia`, `IsCajera` o `IsDueno`.

---

### Requisito 9: Registro de URLs y configuración

**Historia de usuario:** Como desarrollador del equipo Norware, quiero que la app `puerta` esté correctamente integrada en el proyecto Django, para que todos sus endpoints sean accesibles bajo el prefijo `/api/`.

#### Criterios de aceptación

1. THE Sistema SHALL registrar `apps.puerta` en `INSTALLED_APPS` de `settings.py`.
2. THE Sistema SHALL incluir las URLs de la app `puerta` bajo los prefijos `/api/lista/`, `/api/puerta/` y `/api/dashboard/` en `config/urls.py`.
3. THE Sistema SHALL crear las URLs para los endpoints públicos de lista (`GET /api/lista/:slug/` y `POST /api/lista/:slug/anotar/`) en un archivo separado `apps/puerta/lista_urls.py` para claridad.
4. THE Sistema SHALL crear las URLs para los endpoints de guardia y cajera en `apps/puerta/urls.py`.
5. THE Sistema SHALL crear las URLs para el endpoint de aforo en un archivo `apps/puerta/dashboard_urls.py` o incluirlo en el mismo `urls.py` principal según convenga.
