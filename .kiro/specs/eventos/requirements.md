# Documento de Requisitos — App `eventos`

## Introducción

La app `eventos` gestiona los eventos de boliches en la plataforma Norware. Permite a los dueños crear, editar y cancelar eventos. Expone una cartelera pública para que los asistentes consulten precios con desglose en tiempo real. Cada evento posee un `precio_publicado` calculado automáticamente sumando el `precio_base` más los fees de Mercado Pago y Norware. Los eventos nunca se eliminan físicamente; una vez cancelados quedan bloqueados para edición y los reembolsos se delegan a la app `pagos`.

## Glosario

- **Sistema**: la app `eventos` del backend Norware (Django + DRF).
- **Evento**: registro que representa una noche de boliche con aforo, precio, line-up y estado.
- **Boliche**: establecimiento nocturno registrado en la plataforma (modelo en `apps.boliches`).
- **Dueño**: usuario con `rol = 'dueno'` que administra uno o más boliches.
- **precio_base**: precio de venta sin comisiones, definido por el Dueño al crear el Evento.
- **precio_publicado**: precio final que el asistente paga, calculado como `round(precio_base × (1 + FEE_MP_PCT/100 + NORWARE_FEE_PCT/100))`.
- **desglose_precio**: diccionario con `precio_base`, `fee_mp`, `fee_norware` y `precio_publicado`.
- **fee_mp**: comisión de Mercado Pago = `precio_base × FEE_MP_PCT / 100`.
- **fee_norware**: comisión de Norware = `precio_base × NORWARE_FEE_PCT / 100`.
- **FEE_MP_PCT**: porcentaje de fee de Mercado Pago, leído desde `settings.FEE_MP_PCT` (configurado en `.env`).
- **NORWARE_FEE_PCT**: porcentaje de fee de Norware, leído desde `settings.NORWARE_FEE_PCT` (configurado en `.env`).
- **estado**: campo del Evento con valores posibles `activo` o `cancelado`.
- **line_up**: lista JSON de artistas con horarios asociados al Evento.
- **motivo_cancelacion**: texto obligatorio que el Dueño provee al cancelar un Evento.
- **IsDueno**: permiso DRF que valida que el usuario autenticado tenga `rol = 'dueno'`.
- **Calculadora de Precios**: endpoint público que computa el desglose en tiempo real sin crear ni modificar ningún registro.
- **reembolsar_evento**: función en `apps.pagos` que gestiona los reembolsos a compradores web al cancelar un Evento.

---

## Requisitos

### Requisito 1: Modelo de datos del Evento

**Historia de usuario:** Como desarrollador del equipo Norware, quiero un modelo `Evento` con todos los campos de negocio necesarios, para que el resto de las apps de la plataforma puedan relacionarse con él de manera consistente.

#### Criterios de aceptación

1. THE Sistema SHALL definir el modelo `Evento` con los campos: `boliche` (FK a `boliches.Boliche`, `on_delete=PROTECT`), `nombre` (CharField, max 200 caracteres), `fecha` (DateTimeField), `aforo_max` (PositiveIntegerField), `color_pulsera` (CharField, max 50 caracteres), `precio_base` (DecimalField, max_digits=10, decimal_places=2), `line_up` (JSONField, default=list), `estado` (CharField, choices `activo`/`cancelado`, default `activo`), `motivo_cancelacion` (TextField, blank=True, null=True), `created_at` (DateTimeField, auto_now_add=True) y `updated_at` (DateTimeField, auto_now=True).
2. THE Sistema SHALL registrar la app `eventos` en `INSTALLED_APPS` de `settings.py`.
3. THE Sistema SHALL generar y aplicar migraciones para el modelo `Evento` sin conflictos con las migraciones existentes de `cuentas` y `boliches`.
4. THE Sistema SHALL registrar el modelo `Evento` en el panel de administración de Django con al menos los campos `nombre`, `boliche`, `fecha`, `estado` y `precio_base` visibles en el listado.

---

### Requisito 2: Cálculo del precio publicado

**Historia de usuario:** Como dueño de un boliche, quiero ver en tiempo real cuánto pagará el asistente en base al precio que yo defino, para poder ajustar el precio_base antes de publicar el evento.

#### Criterios de aceptación

1. THE Sistema SHALL proveer una función `calcular_precio_publicado(precio_base)` en `apps/eventos/utils.py` que acepte un valor numérico positivo y devuelva un diccionario con las claves `precio_base` (entero), `fee_mp` (float, redondeado a 2 decimales), `fee_norware` (float, redondeado a 2 decimales) y `precio_publicado` (entero redondeado al entero más próximo con ROUND_HALF_UP).
2. WHEN `calcular_precio_publicado` es invocada, THE Sistema SHALL leer `FEE_MP_PCT` y `NORWARE_FEE_PCT` exclusivamente desde `django.conf.settings`, sin hardcodear ningún porcentaje en el código.
3. THE Sistema SHALL calcular `fee_mp` como `precio_base × FEE_MP_PCT / 100` y `fee_norware` como `precio_base × NORWARE_FEE_PCT / 100`, usando aritmética `Decimal` para evitar errores de punto flotante.
4. THE Sistema SHALL calcular `precio_publicado` como `round(precio_base + fee_mp + fee_norware)` aplicando `ROUND_HALF_UP` al entero más próximo.
5. IF `precio_base` no es un número válido o es menor o igual a cero, THEN THE Sistema SHALL lanzar una excepción `ValueError` con un mensaje descriptivo.
6. THE Sistema SHALL configurar en `settings.py` las variables `FEE_MP_PCT = config('FEE_MP_PCT', default=5.99, cast=float)` y `NORWARE_FEE_PCT = config('NORWARE_FEE_PCT', default=8.0, cast=float)`.

---

### Requisito 3: Listado público de eventos

**Historia de usuario:** Como asistente potencial, quiero ver todos los eventos disponibles con su precio publicado, para decidir a cuál ir.

#### Criterios de aceptación

1. WHEN se realiza una petición `GET /api/eventos/`, THE Sistema SHALL responder con código HTTP 200 y una lista de eventos que incluye para cada uno: `id`, `nombre`, `fecha` (ISO 8601 con timezone), `color_pulsera`, `precio_base` (entero), `precio_publicado` (entero), `aforo_max`, `estado`, y `boliche` con sus campos `id`, `nombre` y `direccion`.
2. WHEN se realiza una petición `GET /api/eventos/?estado=activo`, THE Sistema SHALL devolver únicamente los eventos con `estado = 'activo'`.
3. WHEN se realiza una petición `GET /api/eventos/?estado=cancelado`, THE Sistema SHALL devolver únicamente los eventos con `estado = 'cancelado'`.
4. WHEN se realiza una petición `GET /api/eventos/` sin el parámetro `estado`, THE Sistema SHALL devolver todos los eventos sin filtrar por estado.
5. THE Sistema SHALL permitir el acceso a `GET /api/eventos/` sin autenticación.

---

### Requisito 4: Detalle público de un evento

**Historia de usuario:** Como asistente potencial, quiero ver el detalle completo de un evento con el desglose de precios y el line-up, para saber exactamente qué incluye la entrada.

#### Criterios de aceptación

1. WHEN se realiza una petición `GET /api/eventos/:id/` con un ID existente, THE Sistema SHALL responder con código HTTP 200 e incluir todos los campos del listado más: `line_up`, `desglose_precio` (con `precio_base`, `fee_mp`, `fee_norware` y `precio_publicado`), `motivo_cancelacion` y `updated_at`.
2. WHEN se realiza una petición `GET /api/eventos/:id/` con un ID inexistente, THE Sistema SHALL responder con código HTTP 404.
3. THE Sistema SHALL permitir el acceso a `GET /api/eventos/:id/` sin autenticación.

---

### Requisito 5: Creación de eventos

**Historia de usuario:** Como dueño de un boliche, quiero crear nuevos eventos en mi boliche, para gestionar la cartelera y empezar a vender entradas.

#### Criterios de aceptación

1. WHEN un Dueño autenticado realiza una petición `POST /api/eventos/` con los campos requeridos (`boliche_id`, `nombre`, `fecha`, `aforo_max`, `color_pulsera`, `precio_base`, `line_up`), THE Sistema SHALL crear el Evento con `estado = 'activo'` y responder con código HTTP 201 y el detalle completo del evento creado (mismo formato que `GET /api/eventos/:id/`).
2. WHEN una petición `POST /api/eventos/` incluye `boliche_id` cuyo `dueno` no es el usuario autenticado, THE Sistema SHALL responder con código HTTP 403.
3. WHEN una petición `POST /api/eventos/` omite algún campo requerido o envía datos inválidos (por ejemplo, `precio_base` negativo o `aforo_max` igual a cero), THE Sistema SHALL responder con código HTTP 400 y un mensaje descriptivo de los errores de validación.
4. WHEN una petición `POST /api/eventos/` es realizada por un usuario sin autenticación o sin rol `dueno`, THE Sistema SHALL responder con código HTTP 401 o 403 respectivamente.
5. WHEN se crea un Evento, THE Sistema SHALL calcular y persistir `precio_publicado` como campo derivado disponible en la respuesta sin almacenarlo en la base de datos (se calcula en el serializador mediante `calcular_precio_publicado`).

---

### Requisito 6: Edición de eventos

**Historia de usuario:** Como dueño de un boliche, quiero poder editar los detalles de un evento mientras esté activo, para corregir información o ajustar el precio.

#### Criterios de aceptación

1. WHEN un Dueño autenticado realiza una petición `PATCH /api/eventos/:id/` sobre un evento activo que pertenece a su boliche, THE Sistema SHALL actualizar únicamente los campos enviados y responder con código HTTP 200 y el detalle completo del evento actualizado.
2. WHEN un Dueño autenticado realiza una petición `PATCH /api/eventos/:id/` sobre un evento cuyo boliche pertenece a otro Dueño, THE Sistema SHALL responder con código HTTP 403.
3. WHEN se intenta realizar una petición `PATCH /api/eventos/:id/` sobre un evento con `estado = 'cancelado'`, THE Sistema SHALL responder con código HTTP 405.
4. WHEN una petición `PATCH /api/eventos/:id/` envía datos inválidos, THE Sistema SHALL responder con código HTTP 400 y un mensaje descriptivo de los errores de validación.
5. WHEN una petición `PATCH /api/eventos/:id/` es realizada por un usuario sin autenticación o sin rol `dueno`, THE Sistema SHALL responder con código HTTP 401 o 403 respectivamente.

---

### Requisito 7: Cancelación de eventos

**Historia de usuario:** Como dueño de un boliche, quiero poder cancelar un evento indicando el motivo, para notificar a los asistentes y gestionar los reembolsos automáticamente.

#### Criterios de aceptación

1. WHEN un Dueño autenticado realiza una petición `POST /api/eventos/:id/cancelar/` sobre un evento activo de su boliche con un campo `motivo` no vacío, THE Sistema SHALL cambiar el `estado` del Evento a `cancelado`, guardar el `motivo_cancelacion` y responder con código HTTP 200 con el cuerpo `{id, estado, motivo_cancelacion, reembolsos_iniciados}`.
2. WHEN la cancelación es procesada, THE Sistema SHALL invocar `reembolsar_evento(evento_id)` importándola dinámicamente desde `apps.pagos`; IF la función no existe o el módulo no está disponible, THEN THE Sistema SHALL registrar un aviso en el log y continuar sin lanzar una excepción.
3. WHEN una petición `POST /api/eventos/:id/cancelar/` no incluye el campo `motivo` o lo envía vacío (incluyendo cadenas de solo espacios en blanco), THE Sistema SHALL responder con código HTTP 400.
4. WHEN una petición `POST /api/eventos/:id/cancelar/` se realiza sobre un evento con `estado = 'cancelado'`, THE Sistema SHALL responder con código HTTP 409.
5. WHEN una petición `POST /api/eventos/:id/cancelar/` es realizada por un Dueño cuyo boliche no es el del evento, THE Sistema SHALL responder con código HTTP 403.
6. WHEN un Evento es cancelado, THE Sistema SHALL rechazar cualquier intento posterior de edición (`PATCH`) o nueva cancelación, devolviendo 405 y 409 respectivamente.
7. WHEN un Evento es cancelado, THE Sistema SHALL retornar en el campo `reembolsos_iniciados` el número entero de asistentes con `tipo_ingreso = 'web_anticipada'` procesados para reembolso (o 0 si `apps.pagos` no está disponible).

---

### Requisito 8: Prohibición de eliminación de eventos

**Historia de usuario:** Como administrador de la plataforma, quiero que los eventos nunca puedan eliminarse, para preservar el historial de asistentes y transacciones.

#### Criterios de aceptación

1. WHEN se realiza una petición `DELETE /api/eventos/:id/` por cualquier usuario, THE Sistema SHALL responder con código HTTP 405.
2. THE Sistema SHALL devolver código HTTP 405 para `DELETE` independientemente del estado del evento o del rol del usuario que realiza la petición.

---

### Requisito 9: Calculadora de precios en tiempo real

**Historia de usuario:** Como dueño de un boliche, quiero consultar el desglose de precio antes de crear un evento, para entender exactamente cuánto pagará el asistente.

#### Criterios de aceptación

1. WHEN se realiza una petición `GET /api/precios/calcular/?precio_base=X` con un valor numérico positivo, THE Sistema SHALL responder con código HTTP 200 y el cuerpo `{precio_base, fee_mp, fee_norware, precio_publicado}` calculado con la función `calcular_precio_publicado`.
2. WHEN se realiza una petición `GET /api/precios/calcular/` sin el parámetro `precio_base`, THE Sistema SHALL responder con código HTTP 400.
3. WHEN se realiza una petición `GET /api/precios/calcular/?precio_base=X` con un valor no numérico o menor o igual a cero, THE Sistema SHALL responder con código HTTP 400 con un mensaje descriptivo.
4. THE Sistema SHALL permitir el acceso a `GET /api/precios/calcular/` sin autenticación.

---

### Requisito 10: Registro de URLs y configuración

**Historia de usuario:** Como desarrollador del equipo Norware, quiero que la app `eventos` esté correctamente integrada en el proyecto Django, para que todos sus endpoints sean accesibles bajo el prefijo `/api/`.

#### Criterios de aceptación

1. THE Sistema SHALL registrar `apps.eventos` en `INSTALLED_APPS` de `settings.py`.
2. THE Sistema SHALL incluir las URLs de la app `eventos` bajo el prefijo `/api/` en `config/urls.py`, incluyendo tanto los endpoints de eventos como el de la calculadora de precios (`/api/precios/calcular/`).
3. THE Sistema SHALL incluir las variables `FEE_MP_PCT` y `NORWARE_FEE_PCT` en `settings.py` leyéndolas con `python-decouple`.
