# Documento de Requisitos — App `rrpp`

## Introducción

La app `rrpp` implementa el módulo de Relaciones Públicas de la plataforma Norware. Permite a los dueños de boliche gestionar a sus RRPPs (relacionistas públicos), asignarlos a eventos y hacer un seguimiento de su rendimiento. Cada RRPP tiene links únicos por evento para captar asistentes y el sistema rastrea en tiempo real cuántos de esos asistentes terminan ingresando al boliche.

El módulo cubre tres actores: el **Dueño** (gestiona RRPPs y asignaciones), el **RRPP** (ve su panel personal y carga invitados), y el sistema automático que genera links al asignar un RRPP a un evento.

## Glosario

- **Sistema**: El backend Django de Norware (`apps/rrpp`).
- **RRPP**: Relacionista público. Usuario con `rol=rrpp` que tiene un perfil de comisión asociado a un boliche.
- **Asignacion**: Relación entre un RRPP y un Evento concreto. Habilita al RRPP para trabajar en ese evento.
- **LinkRRPP**: Link único (UUID slug) que el RRPP comparte con sus invitados. Existen dos tipos: `lista` (para que los invitados se anoten) y `venta_web` (para que compren entradas online).
- **Asistente**: Registro en `apps.puerta` de una persona que concurrirá o concurrió al evento. Tiene estados: `pendiente`, `aprobado_guardia`, `rebotado_guardia`, `ingresado_final`.
- **Dueño**: Usuario con `rol=dueno`. Es el dueño del boliche y administra sus RRPPs.
- **Boliche**: Local nocturno registrado en el sistema (`apps.boliches.Boliche`).
- **Evento**: Fiesta o evento registrado en el sistema (`apps.eventos.Evento`), asociado a un Boliche.
- **Comision_Fija**: Modalidad de comisión donde el RRPP cobra un monto fijo en ARS por cada asistente ingresado.
- **Comision_Porcentaje**: Modalidad de comisión donde el RRPP cobra un porcentaje del monto total recaudado atribuido a sus links.
- **IsDueno**: Permission class de DRF que verifica que el usuario autenticado tenga `rol=dueno`.
- **IsRRPP**: Permission class de DRF que verifica que el usuario autenticado tenga `rol=rrpp`.

---

## Requisitos

### Requisito 1: Alta de RRPP

**Historia de usuario:** Como dueño de boliche, quiero dar de alta un nuevo RRPP en mi boliche, para que pueda gestionar invitados en mis eventos.

#### Criterios de aceptación

1. WHEN un Dueño envía `POST /api/rrpp/` con nombre, apellido, username, password, telefono, tipo_comision y valor_comision válidos, THE Sistema SHALL crear un Usuario con `rol=rrpp` y un perfil RRPP asociado al boliche del Dueño dentro de una única transacción atómica, y responder con HTTP 201 y los datos del RRPP creado.
2. WHEN la creación del Usuario falla durante el alta de RRPP (por ejemplo, username duplicado), THE Sistema SHALL revertir toda la transacción y no persistir ningún objeto parcial (ni Usuario ni RRPP).
3. IF el username enviado ya existe en la base de datos, THEN THE Sistema SHALL responder con HTTP 400 y un mensaje de error indicando que el username no está disponible.
4. IF el Dueño no envía alguno de los campos requeridos (nombre, apellido, username, password, tipo_comision, valor_comision), THEN THE Sistema SHALL responder con HTTP 400 indicando qué campos faltan.
5. IF el usuario autenticado no tiene `rol=dueno`, THEN THE Sistema SHALL responder con HTTP 403.
6. THE Sistema SHALL asignar el RRPP creado al mismo boliche del Dueño autenticado que ejecuta la petición.

---

### Requisito 2: Listado de RRPPs del boliche

**Historia de usuario:** Como dueño de boliche, quiero ver todos mis RRPPs con sus asignaciones y links, para tener una visión completa de mi equipo de relaciones públicas.

#### Criterios de aceptación

1. WHEN un Dueño envía `GET /api/rrpp/`, THE Sistema SHALL devolver únicamente los RRPPs asociados al boliche del Dueño autenticado.
2. THE Sistema SHALL incluir en cada RRPP de la respuesta sus asignaciones activas e inactivas, y dentro de cada asignación los links con tipo, slug y URL pública.
3. IF el usuario autenticado no tiene `rol=dueno`, THEN THE Sistema SHALL responder con HTTP 403.

---

### Requisito 3: Asignación de RRPP a evento

**Historia de usuario:** Como dueño de boliche, quiero asignar un RRPP a un evento de mi boliche, para que pueda trabajar en ese evento y se generen sus links automáticamente.

#### Criterios de aceptación

1. WHEN un Dueño envía `POST /api/rrpp/:id/asignar-evento/` con un `evento_id` válido perteneciente a su boliche, THE Sistema SHALL crear una Asignacion entre el RRPP y el Evento, y responder con HTTP 201 incluyendo los datos de la asignación y los links generados.
2. WHEN se crea una Asignacion nueva (signal `post_save` con `created=True`), THE Sistema SHALL crear exactamente 2 instancias de LinkRRPP: una de tipo `lista` y otra de tipo `venta_web`, cada una con un slug UUID v4 único.
3. THE Sistema SHALL garantizar que los slugs de los LinkRRPP generados son únicos en todo el sistema (no colisionan con slugs existentes).
4. IF el `evento_id` enviado no existe o no pertenece al boliche del Dueño autenticado, THEN THE Sistema SHALL responder con HTTP 400 con un mensaje descriptivo.
5. IF el RRPP ya está asignado al evento indicado, THEN THE Sistema SHALL responder con HTTP 409.
6. IF el usuario autenticado no tiene `rol=dueno`, THEN THE Sistema SHALL responder con HTTP 403.

---

### Requisito 4: Panel del RRPP

**Historia de usuario:** Como RRPP, quiero ver mi panel personal con las métricas de mis asignaciones activas, para saber cuántos invitados anoté, cuántos ingresaron y cuántos fueron rebotados.

#### Criterios de aceptación

1. WHEN un RRPP autenticado envía `GET /api/rrpp/mi-panel/`, THE Sistema SHALL devolver únicamente las asignaciones activas (`activa=True`) del RRPP autenticado.
2. THE Sistema SHALL incluir en cada asignación las estadísticas en tiempo real consultadas desde `apps.puerta.Asistente`: cantidad de anotados (todos los Asistentes del evento con link del RRPP), ingresados (`estado=ingresado_final`), pendientes (`estado=pendiente` o `estado=aprobado_guardia`), y rebotados (`estado=rebotado_guardia`).
3. THE Sistema SHALL incluir en cada asignación los datos del evento (id, nombre, fecha, color_pulsera) y los links del RRPP para ese evento (tipo, slug, URL pública).
4. IF el usuario autenticado no tiene `rol=rrpp`, THEN THE Sistema SHALL responder con HTTP 403.
5. WHILE un RRPP está autenticado, THE Sistema SHALL mostrar únicamente sus propias asignaciones y nunca datos de otros RRPPs.

---

### Requisito 5: Anotación manual de invitado por RRPP

**Historia de usuario:** Como RRPP, quiero anotar manualmente un invitado en mi lista, para poder agregar personas que me contactan por medios externos al link público.

#### Criterios de aceptación

1. WHEN un RRPP autenticado envía `POST /api/rrpp/anotar-invitado/` con slug_lista, nombre, apellido y dni válidos, THE Sistema SHALL crear un Asistente con `tipo_ingreso=lista_rrpp` y `estado=pendiente` asociado al link indicado, y responder con HTTP 201.
2. IF el slug_lista enviado no existe o corresponde a un LinkRRPP que no pertenece al RRPP autenticado, THEN THE Sistema SHALL responder con HTTP 403.
3. IF ya existe un Asistente con el mismo DNI en el mismo Evento, THEN THE Sistema SHALL responder con HTTP 409.
4. IF el RRPP no envía alguno de los campos requeridos (slug_lista, nombre, apellido, dni), THEN THE Sistema SHALL responder con HTTP 400 indicando qué campos faltan.
5. IF el LinkRRPP tiene `activo=False`, THEN THE Sistema SHALL responder con HTTP 410 indicando que el link está inactivo.

---

### Requisito 6: Desactivación de links al cancelar evento

**Historia de usuario:** Como sistema, necesito que cuando un evento se cancela, todos los links de RRPP asociados queden inactivos, para evitar que los invitados se sigan anotando.

#### Criterios de aceptación

1. WHEN un Evento cambia su `estado` a `cancelado`, THE Sistema SHALL marcar como `activo=False` todos los LinkRRPP cuya asignación esté relacionada con ese Evento.
2. WHEN un LinkRRPP tiene `activo=False`, THE Sistema SHALL rechazar nuevas anotaciones de invitados respondiendo con HTTP 410.
3. THE Sistema SHALL ejecutar la desactivación masiva de links de forma atómica con el cambio de estado del evento.

---

### Requisito 7: Aislamiento de permisos entre RRPPs

**Historia de usuario:** Como sistema, necesito garantizar que un RRPP no pueda acceder a datos ni realizar acciones sobre los links de otro RRPP, para proteger la integridad de la información.

#### Criterios de aceptación

1. IF un RRPP intenta anotar un invitado usando el slug de un LinkRRPP que pertenece a otro RRPP, THEN THE Sistema SHALL responder con HTTP 403.
2. WHILE un RRPP está autenticado y accede a `GET /api/rrpp/mi-panel/`, THE Sistema SHALL excluir de la respuesta cualquier asignación o estadística que no corresponda al RRPP autenticado.

---

### Requisito 8: Integridad de la señal de generación de links

**Historia de usuario:** Como sistema, necesito garantizar que cada vez que se crea una AsignacionRRPP se generen exactamente 2 links (uno de lista y uno de venta_web), para que el RRPP siempre tenga ambos canales disponibles.

#### Criterios de aceptación

1. WHEN se dispara el signal `post_save` de AsignacionRRPP con `created=True`, THE Sistema SHALL crear exactamente un LinkRRPP de tipo `lista` y exactamente un LinkRRPP de tipo `venta_web` asociados a esa asignación.
2. THE Sistema SHALL garantizar que el signal solo crea links cuando `created=True` (nueva creación) y no cuando la Asignacion es actualizada (`created=False`).
3. THE Sistema SHALL generar slugs UUID v4 para cada LinkRRPP mediante `uuid.uuid4()`, asegurando unicidad global.
