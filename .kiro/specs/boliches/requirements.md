# Documento de Requisitos — App `boliches`

## Introducción

La app `boliches` gestiona el modelo central `Boliche` de la plataforma Norware. Un boliche representa el local físico de un organizador de eventos. Cada dueño puede registrar su boliche, indicando su nombre, dirección y el ID de su cuenta de Mercado Pago (`collector_id_mp`), que se utiliza para enrutar los cobros de entradas hacia su cuenta. Esta app expone tres endpoints REST protegidos por el permiso `IsDueno`: consulta del boliche propio, creación y edición parcial.

---

## Glosario

- **Boliche**: Entidad que representa un local nocturno registrado en Norware. Tiene nombre, dirección, dueño y `collector_id_mp`.
- **Dueño**: Usuario con `rol='dueno'` en el sistema. Propietario de un boliche.
- **collector_id_mp**: Identificador público numérico de la cuenta de Mercado Pago del dueño. Se usa para enrutar pagos de entradas a su cuenta vía `application_fee`.
- **IsDueno**: Permiso custom de DRF definido en `apps.cuentas.permissions`. Permite el acceso solo a usuarios autenticados con `rol='dueno'`.
- **API**: Interfaz REST implementada con Django REST Framework.
- **Sistema**: El backend Django de Norware.

---

## Requisitos

### Requisito 1: Creación de boliche

**Historia de usuario:** Como dueño autenticado, quiero registrar mi boliche con nombre, dirección y mi ID de Mercado Pago, para poder crear eventos y recibir pagos en mi cuenta.

#### Criterios de aceptación

1. WHEN un dueño autenticado envía una solicitud `POST /api/boliches/` con `nombre`, `direccion` y `collector_id_mp` válidos, THE Sistema SHALL crear un `Boliche` asociado a ese dueño y devolver el recurso creado con código HTTP 201.
2. WHEN un dueño autenticado envía una solicitud `POST /api/boliches/` con uno o más campos requeridos ausentes, THE Sistema SHALL rechazar la solicitud y devolver un error con código HTTP 400 que indique los campos faltantes.
3. WHEN un dueño autenticado que ya posee un boliche envía una solicitud `POST /api/boliches/`, THE Sistema SHALL rechazar la solicitud y devolver un error con código HTTP 409.
4. WHEN un usuario autenticado con rol distinto de `dueno` envía una solicitud `POST /api/boliches/`, THE Sistema SHALL rechazar la solicitud con código HTTP 403.
5. WHEN un usuario no autenticado envía una solicitud `POST /api/boliches/`, THE Sistema SHALL rechazar la solicitud con código HTTP 401.
6. THE Sistema SHALL asociar el `Boliche` creado al dueño autenticado extraído del token JWT, sin aceptar el campo `dueno` en el cuerpo de la solicitud.

### Requisito 2: Consulta del boliche propio

**Historia de usuario:** Como dueño autenticado, quiero consultar los datos de mi boliche, para poder verificar mi configuración de Mercado Pago y los datos del local.

#### Criterios de aceptación

1. WHEN un dueño autenticado envía una solicitud `GET /api/boliches/mio/`, THE Sistema SHALL devolver los datos del boliche que pertenece a ese dueño con código HTTP 200.
2. WHEN un dueño autenticado que no tiene ningún boliche registrado envía una solicitud `GET /api/boliches/mio/`, THE Sistema SHALL devolver un error con código HTTP 404.
3. WHEN un usuario autenticado con rol distinto de `dueno` envía una solicitud `GET /api/boliches/mio/`, THE Sistema SHALL rechazar la solicitud con código HTTP 403.
4. THE Sistema SHALL incluir en la respuesta de `GET /api/boliches/mio/` los campos `id`, `nombre`, `direccion`, `collector_id_mp` y `created_at`.
5. THE Sistema SHALL excluir el campo `dueno` (objeto usuario completo) de la respuesta serializada del boliche.

### Requisito 3: Edición parcial del boliche

**Historia de usuario:** Como dueño autenticado, quiero editar el nombre, la dirección o el `collector_id_mp` de mi boliche, para poder mantener actualizados los datos del local y de mi cuenta de Mercado Pago.

#### Criterios de aceptación

1. WHEN un dueño autenticado envía una solicitud `PATCH /api/boliches/:id/` con un subconjunto válido de campos editables, THE Sistema SHALL actualizar únicamente los campos provistos y devolver el recurso actualizado con código HTTP 200.
2. WHEN un dueño autenticado envía una solicitud `PATCH /api/boliches/:id/` referenciando un boliche que no le pertenece, THE Sistema SHALL rechazar la solicitud con código HTTP 403.
3. WHEN cualquier cliente envía una solicitud `PATCH /api/boliches/:id/` con un `id` que no existe en la base de datos, THE Sistema SHALL devolver un error con código HTTP 404.
4. THE Sistema SHALL permitir editar únicamente los campos `nombre`, `direccion` y `collector_id_mp` en el endpoint `PATCH /api/boliches/:id/`.
5. THE Sistema SHALL ignorar cualquier intento de modificar el campo `dueno` o `created_at` a través del endpoint `PATCH /api/boliches/:id/`.

### Requisito 4: Restricción de eliminación

**Historia de usuario:** Como administrador del sistema, quiero que los boliches no puedan eliminarse vía API, para preservar la integridad de los datos históricos de eventos y asistentes.

#### Criterios de aceptación

1. WHEN cualquier cliente envía una solicitud `DELETE /api/boliches/:id/`, THE Sistema SHALL rechazar la solicitud con código HTTP 405.

### Requisito 5: Formato de respuesta del boliche

**Historia de usuario:** Como desarrollador frontend, quiero que todos los endpoints de boliches devuelvan un formato de respuesta consistente, para poder integrar la API sin ambigüedades.

#### Criterios de aceptación

1. THE Sistema SHALL serializar el campo `created_at` en formato ISO 8601 con timezone en todas las respuestas de boliche.
2. THE Sistema SHALL serializar el campo `collector_id_mp` como una cadena de texto en todas las respuestas, sin importar su valor numérico.
3. WHEN el Sistema devuelve una respuesta exitosa de boliche, THE Sistema SHALL incluir exactamente los campos: `id` (entero), `nombre` (string), `direccion` (string), `collector_id_mp` (string) y `created_at` (string ISO 8601).

### Requisito 6: Registro e integración de la app

**Historia de usuario:** Como desarrollador del backend, quiero que la app `boliches` esté correctamente registrada en Django y su router integrado en las URLs del proyecto, para que los endpoints sean accesibles bajo el prefijo `/api/boliches/`.

#### Criterios de aceptación

1. THE Sistema SHALL registrar `apps.boliches` en `INSTALLED_APPS` en `config/settings.py`.
2. THE Sistema SHALL incluir las URLs de la app `boliches` bajo el prefijo `/api/boliches/` en `config/urls.py`.
3. THE Sistema SHALL crear y aplicar las migraciones necesarias para el modelo `Boliche` en la base de datos.
4. THE Sistema SHALL registrar el modelo `Boliche` en el panel de administración de Django (`admin.py`).
