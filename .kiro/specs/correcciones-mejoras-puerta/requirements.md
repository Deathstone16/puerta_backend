# Requirements Document

## Introduction

Este documento cubre correcciones de bugs, mejoras de seguridad y mejoras de UX para la plataforma Puerta — un sistema de gestión de eventos nocturnos con roles de Dueño/Organizador, RRPP (promotores), Guardia, Cajera y Superadmin. Los issues están priorizados por impacto en la integridad de datos y seguridad multi-tenant.

## Glossary

- **Sistema**: La plataforma Puerta (backend Django REST + frontend React).
- **Dueño**: Usuario con rol `dueno` que administra boliches y crea eventos (noches).
- **RRPP**: Personal promotor asignado por un Dueño a eventos; carga invitados en listas.
- **Superadmin**: Usuario con rol `superadmin` que gestiona cuentas de Dueños.
- **Evento**: Una "noche" o fecha con lineup, precio y aforo máximo, creada por un Dueño.
- **Asignación_RRPP**: Relación entre un RRPP y un Evento, con tipo y valor de comisión.
- **Personal**: Cualquier usuario staff (RRPP, Guardia, Cajera) creado por un Dueño.
- **Panel_RRPP**: Vista donde el RRPP ve sus eventos asignados y gestiona invitados.
- **Panel_Admin**: Vista donde el Superadmin gestiona organizadores.
- **Invitado**: Registro de Asistente vinculado a un Evento y opcionalmente a un LinkRRPP.
- **QuerySet**: Conjunto filtrado de objetos que un endpoint devuelve al cliente.

---

## Requirements

### Requirement 1: Aislamiento de datos de eventos por Dueño

**User Story:** Como Dueño, quiero ver únicamente mis propios eventos, para que la información de otros organizadores no sea accesible desde mi sesión.

**Prioridad:** ALTA

#### Acceptance Criteria

1. WHEN un Dueño autenticado solicita la lista de eventos con el parámetro `mis_eventos`, THE Sistema SHALL retornar exclusivamente los eventos donde el campo `organizador` coincida con el Dueño autenticado, excluyendo todos los eventos de otros organizadores del resultado.
2. WHEN un Dueño autenticado solicita el detalle (GET) de un evento cuyo `organizador` es otro usuario, THE Sistema SHALL retornar un código HTTP 403 sin revelar el contenido del evento.
3. WHEN un Dueño autenticado intenta editar (PATCH) un evento cuyo `organizador` es otro usuario, THE Sistema SHALL retornar un código HTTP 403 sin modificar ningún campo del evento.
4. WHEN un Dueño autenticado intenta cancelar (POST cancelar) un evento cuyo `organizador` es otro usuario, THE Sistema SHALL retornar un código HTTP 403 sin modificar el estado del evento.
5. IF un Dueño autenticado solicita detalle, edición o cancelación de un evento con un ID inexistente, THEN THE Sistema SHALL retornar un código HTTP 404.
6. THE Sistema SHALL aplicar el filtro de propiedad por `organizador` en todos los endpoints de eventos que utilizan el permiso IsDueno: creación, edición (PATCH), cancelación y listado filtrado (`mis_eventos`).

---

### Requirement 2: Aislamiento de datos de RRPP y asignaciones por Dueño

**User Story:** Como Dueño, quiero que al asignar RRPP a eventos solo se muestren los eventos que me pertenecen, para evitar filtraciones de datos entre organizadores.

**Prioridad:** ALTA

#### Acceptance Criteria

1. WHEN un Dueño solicita la lista de RRPP, THE Sistema SHALL retornar exclusivamente los RRPP cuyo campo `organizador` coincida con el Dueño autenticado, excluyendo aquellos cuyo usuario asociado tenga `is_active=False`.
2. WHEN un Dueño solicita eventos disponibles para asignar a un RRPP, THE Sistema SHALL listar únicamente eventos cuyo `organizador` sea el Dueño autenticado, cuyo `estado` sea `activo`, y que no estén ya asignados a ese RRPP, ordenados por fecha descendente.
3. WHEN un Dueño intenta asignar un RRPP a un evento cuyo `organizador` no coincide con el Dueño autenticado, THE Sistema SHALL retornar un código HTTP 400 con un mensaje de error indicando que el evento no le pertenece, sin crear ni modificar la asignación.
4. WHEN un Dueño intenta consultar, editar o eliminar un RRPP cuyo campo `organizador` no coincide con el Dueño autenticado, THE Sistema SHALL retornar un código HTTP 403 sin revelar datos del RRPP ajeno.
5. WHEN un Dueño intenta asignar un RRPP que pertenece a otro Dueño a uno de sus propios eventos, THE Sistema SHALL retornar un código HTTP 403 sin crear la asignación.

---

### Requirement 3: Eliminación (desactivación) de RRPP

**User Story:** Como Dueño, quiero poder eliminar (desactivar) un RRPP, para que deje de tener acceso al sistema y a los eventos.

**Prioridad:** ALTA

#### Acceptance Criteria

1. WHEN un Dueño ejecuta la acción eliminar sobre un RRPP que le pertenece (el RRPP fue creado por ese Dueño), THE Sistema SHALL marcar el usuario asociado como inactivo (`is_active=False`) y responder con código HTTP 200 y un mensaje de confirmación.
2. WHEN un RRPP es desactivado, THE Sistema SHALL desactivar todas las Asignación_RRPP asociadas a ese RRPP (`activa=False`).
3. IF el Dueño intenta eliminar un RRPP que no le pertenece, THEN THE Sistema SHALL responder con código HTTP 403 sin modificar ningún dato.
4. IF el RRPP indicado por el identificador no existe, THEN THE Sistema SHALL responder con código HTTP 404.
5. WHEN el Dueño lista su Personal después de eliminar un RRPP, THE Sistema SHALL excluir de la lista a todos los RRPP cuyo usuario tenga `is_active=False`.
6. WHEN un RRPP desactivado intenta autenticarse, THE Sistema SHALL rechazar el inicio de sesión indicando que la cuenta está inactiva.

---

### Requirement 4: Persistencia de invitados cargados por RRPP

**User Story:** Como RRPP, quiero que los invitados que cargo queden guardados permanentemente, para poder consultarlos y que aparezcan en la lista del evento.

**Prioridad:** ALTA

#### Acceptance Criteria

1. WHEN un RRPP autenticado envía una solicitud de anotación con los campos `slug_lista`, `nombre`, `apellido` y `dni`, THE Sistema SHALL crear un registro de Asistente persistido en base de datos con `tipo_ingreso=lista_rrpp` y `estado=pendiente`, asociado al Evento y al LinkRRPP correspondiente al `slug_lista` proporcionado, y responder con HTTP 201 incluyendo el id, nombre completo, dni, instagram y estado del invitado creado.
2. WHEN un RRPP autenticado consulta su panel, THE Sistema SHALL retornar para cada asignación activa los últimos 20 invitados cargados para ese link ordenados por fecha de creación descendente, incluyendo id, nombre, apellido, dni, instagram, estado y fecha de creación de cada uno.
3. IF la solicitud de anotación no incluye el campo `slug_lista` o lo envía vacío, THEN THE Sistema SHALL retornar HTTP 400 con un mensaje indicando que los campos slug_lista, nombre, apellido y dni son obligatorios.
4. IF el `slug_lista` enviado no corresponde a un LinkRRPP existente de tipo lista, THEN THE Sistema SHALL retornar HTTP 404 indicando que el link no fue encontrado.
5. IF ya existe un Asistente con el mismo DNI en el mismo Evento, THEN THE Sistema SHALL retornar HTTP 409 indicando que el DNI ya está registrado en el evento.

---

### Requirement 5: Visibilidad de eventos asignados para RRPP

**User Story:** Como RRPP, quiero ver los eventos a los que estoy asignado y su información, para poder gestionar mis listas de invitados.

**Prioridad:** ALTA

#### Acceptance Criteria

1. WHEN un RRPP autenticado realiza un GET al endpoint del Panel_RRPP, THE Sistema SHALL retornar todas las Asignación_RRPP con campo activa=true asociadas al perfil RRPP del usuario, incluyendo por cada asignación: evento_id, evento_nombre, evento_fecha, color_pulsera, tipo_comision, valor_comision, y la lista de links asociados (cada uno con tipo, slug, activo, y url).
2. WHEN el Sistema retorna asignaciones activas en el Panel_RRPP, THE Sistema SHALL incluir por cada asignación un objeto de estadísticas con los contadores: anotados, ingresados, pendientes, rebotados, y la lista de hasta 20 invitados recientes ordenados por fecha de creación descendente.
3. IF un RRPP autenticado no tiene asignaciones con campo activa=true, THEN THE Sistema SHALL retornar una lista vacía con código HTTP 200.
4. IF un usuario autenticado no tiene rol 'rrpp', THEN THE Sistema SHALL rechazar la solicitud al Panel_RRPP con código HTTP 403.
5. IF un usuario con rol 'rrpp' no tiene un perfil RRPP asociado en la base de datos, THEN THE Sistema SHALL responder con código HTTP 404 indicando que el recurso no fue encontrado.

---

### Requirement 6: Edición completa de eventos

**User Story:** Como Dueño, quiero editar todos los campos de un evento existente, para corregir información o actualizar detalles de la noche.

#### Acceptance Criteria

1. WHEN un Dueño abre la edición de un evento, THE Sistema SHALL presentar un formulario precargado con todos los datos actuales del evento (nombre, fecha, aforo_max, color_pulsera, precio_base, line_up, habilitar_lista) obtenidos del endpoint de detalle del evento.
2. WHEN un Dueño envía el formulario de edición con al menos un campo modificado, THE Sistema SHALL enviar una solicitud PATCH incluyendo únicamente los campos cuyos valores difieren de los datos precargados originales.
3. THE Sistema SHALL reutilizar el mismo componente de formulario para creación y edición de eventos, diferenciándolos por modo (crear vs. editar), donde el modo editar precarga los valores existentes y el modo crear inicia con campos vacíos o sus valores por defecto.
4. IF un Dueño intenta editar un evento en estado "cancelado", THEN THE Sistema SHALL mostrar un mensaje de error indicando que un evento cancelado no es editable y no permitir el envío del formulario.
5. IF el Dueño envía el formulario de edición sin modificar ningún campo, THEN THE Sistema SHALL no realizar ninguna solicitud al servidor y mantener el formulario abierto sin cambios.
6. IF la solicitud PATCH falla por error de validación del servidor, THEN THE Sistema SHALL mostrar los mensajes de error asociados a cada campo inválido sin descartar los datos ingresados por el usuario en el formulario.

---

### Requirement 7: Formulario de evento responsivo

**User Story:** Como Dueño, quiero que el formulario de "Nueva noche" / edición se adapte a mi pantalla, para poder operar desde dispositivos móviles y desktop sin que el contenido se corte.

#### Acceptance Criteria

1. THE Sistema SHALL renderizar el modal de formulario de evento dentro del viewport visible en tres rangos de ancho: mobile (ancho < 768px), tablet (768px <= ancho < 1024px) y desktop (ancho >= 1024px), sin que ningún contenido quede cortado u oculto fuera de los límites de la pantalla.
2. WHEN el contenido del modal excede la altura disponible del viewport (altura del panel del modal > 90vh), THE Sistema SHALL activar scroll vertical interno dentro del panel del modal, manteniendo el overlay de fondo fijo.
3. THE Sistema SHALL mantener los botones de acción (Guardar/Cancelar) siempre accesibles dentro del panel del modal mediante scroll interno, sin requerir scroll de la página subyacente.
4. WHILE el viewport tiene un ancho menor a 768px, THE Sistema SHALL expandir el ancho del panel del modal al 100% del espacio disponible (restando el padding exterior de 16px por lado).

---

### Requirement 8: Corrección de etiqueta "Aforo"

**User Story:** Como Dueño, quiero que la etiqueta del campo de capacidad diga "Máximo de personas" en lugar de "Aforo", para mayor claridad.

#### Acceptance Criteria

1. THE Sistema SHALL mostrar la etiqueta "Máximo de personas" en el campo `aforo_max` del formulario de creación y edición de eventos, reemplazando cualquier texto que contenga "Aforo".
2. THE Sistema SHALL mantener el nombre del campo del modelo backend como `aforo_max` sin cambios (solo se modifica la etiqueta visual en el frontend).
3. WHEN el campo `aforo_max` falla la validación del lado cliente, THE Sistema SHALL mostrar el mensaje de error usando la nueva etiqueta (e.g., "Máximo de personas" en lugar de "Aforo") para mantener consistencia con la etiqueta visible.

---

### Requirement 9: Gestión de organizadores desde Panel_Admin (editar, eliminar, reactivar)

**User Story:** Como Superadmin, quiero editar, eliminar y reactivar cuentas de organizadores desde el panel de administración, para gestionar el ciclo de vida completo de las cuentas.

#### Acceptance Criteria

1. WHEN un Superadmin edita un organizador, THE Sistema SHALL permitir modificar nombre (máximo 150 caracteres), apellido (máximo 150 caracteres), email, teléfono (máximo 20 caracteres) y username (máximo 150 caracteres), y retornar HTTP 200 con los datos actualizados del organizador.
2. IF un Superadmin intenta editar un organizador con un username o email que ya existe en otro usuario, THEN THE Sistema SHALL rechazar la operación con un error de validación indicando el campo duplicado.
3. WHEN un Superadmin elimina (desactiva) un organizador, THE Sistema SHALL marcar el usuario como inactivo (`is_active=False`) y retornar HTTP 204.
4. WHEN un Superadmin desea resetear la contraseña de un organizador, THE Sistema SHALL aceptar un nuevo password de mínimo 8 caracteres y almacenarlo con hash seguro (bcrypt/PBKDF2) sin revelar la contraseña anterior.
5. THE Sistema SHALL rechazar cualquier solicitud de mostrar la contraseña en texto plano de un organizador; las contraseñas se almacenan exclusivamente con hash irreversible.
6. WHEN un Superadmin reactiva un organizador previamente desactivado (`is_active=False`), THE Sistema SHALL marcar el usuario como activo (`is_active=True`) y retornar HTTP 200 con los datos actualizados.
7. THE Sistema SHALL incluir organizadores activos e inactivos en el listado del Panel_Admin, indicando el estado (`is_active`) de cada uno, ordenados por fecha de creación descendente.

---

### Requirement 10: Listado consistente de organizadores en Panel_Admin

**User Story:** Como Superadmin, quiero que el listado de organizadores siempre muestre todos los organizadores (activos e inactivos), para tener visibilidad completa del estado de las cuentas.

**Prioridad:** ALTA

#### Acceptance Criteria

1. THE Sistema SHALL retornar todos los usuarios con rol `dueno` en el endpoint de listado de organizadores, independientemente de su estado `is_active`, ordenados por fecha de creación descendente.
2. WHEN un Superadmin consulta el endpoint de listado de organizadores después de cualquier operación de creación, edición, desactivación o reactivación, THE Sistema SHALL retornar la lista completa y actualizada sin requerir operaciones adicionales para refrescar los datos.
3. THE Sistema SHALL incluir los campos `id`, `username`, `nombre`, `email`, `telefono`, `is_active` y `date_joined` en la respuesta de cada organizador para que el frontend pueda distinguir visualmente activos de inactivos.

---

### Requirement 11: Desactivación en cascada de Personal al desactivar Dueño

**User Story:** Como Superadmin, quiero que al desactivar un organizador se desactiven automáticamente todos sus RRPP y personal asociado, para evitar que personal huérfano acceda al sistema.

**Prioridad:** ALTA

#### Acceptance Criteria

1. WHEN un Superadmin desactiva un organizador, THE Sistema SHALL establecer `is_active=False` en todos los usuarios cuyo perfil RRPP (`perfil_rrpp.organizador`) apunte al organizador desactivado.
2. WHEN un Superadmin desactiva un organizador, THE Sistema SHALL establecer `is_active=False` en todos los usuarios con rol staff (guardia, cajera) cuyo campo `organizador` apunte al organizador desactivado.
3. WHEN un Superadmin desactiva un organizador, THE Sistema SHALL establecer `activa=False` en todas las AsignacionRRPP pertenecientes a los RRPP asociados al organizador desactivado, y establecer `activo=False` en todos los LinkRRPP asociados a dichas asignaciones.
4. WHEN un Superadmin desactiva un organizador, THE Sistema SHALL establecer `activa=False` en todas las AsignacionStaff pertenecientes al personal (guardia, cajera) asociado al organizador desactivado.
5. THE Sistema SHALL ejecutar la desactivación del organizador y toda la cascada (criterios 1-4) dentro de una única transacción atómica; IF cualquier operación dentro de la transacción falla, THEN THE Sistema SHALL revertir todos los cambios y retornar un error indicando que la desactivación no pudo completarse.
6. IF el organizador ya se encuentra inactivo (`is_active=False`) al momento de la solicitud, THEN THE Sistema SHALL retornar una respuesta exitosa sin modificar ningún registro asociado.

---

### Requirement 12: Corrección de logo duplicado en pantalla de login

**User Story:** Como usuario, quiero ver un único logo en la pantalla de login, para que la interfaz se vea profesional y sin elementos redundantes.

#### Acceptance Criteria

1. WHEN la pantalla de login se renderiza dentro de PublicLayout, THE Sistema SHALL ocultar el logo de la barra de navegación del PublicLayout, de modo que el único logo visible sea el renderizado por la propia LoginPage en su panel izquierdo (desktop) o en el encabezado del formulario (mobile).
2. THE Sistema SHALL mostrar exactamente una instancia visible del componente PuertaLogo en la pantalla de login en cualquier viewport (mobile, tablet o desktop).
3. IF el viewport es menor a 1024px (breakpoint `lg`), THEN THE Sistema SHALL mostrar el logo únicamente en el encabezado del formulario de login, ya que el panel izquierdo decorativo está oculto.
4. THE Sistema SHALL mantener visible el logo en el footer de PublicLayout sin considerarlo duplicado, dado que el footer está fuera del viewport inicial (below the fold).

---

### Requirement 13: Scroll interno en panel "RRPP asignados" dentro de tarjeta de evento

**User Story:** Como Dueño, quiero que el listado de RRPP asignados a un evento tenga scroll interno cuando hay muchos, para poder verlos todos sin que se corte el contenido.

#### Acceptance Criteria

1. WHEN el panel expandido de personal (EventoPersonalPanel) contiene contenido que excede 320px de altura, THE Sistema SHALL activar scroll vertical interno limitando la altura máxima del contenedor a 320px con overflow-y auto.
2. THE Sistema SHALL asegurar que el contenedor padre de cada tarjeta de evento en NochesTab no aplique `overflow: hidden` que recorte el panel expandido de personal.
3. WHEN el dropdown de búsqueda de personal dentro del panel se despliega, THE Sistema SHALL mantenerlo completamente visible sin recortarse por el contenedor con scroll, posicionándolo con z-index superior o portal fuera del contenedor scrolleable.
4. THE Sistema SHALL mantener el estilo visual existente del panel (fondo oscuro `dark:bg-void/50`, bordes `border-white/10`, tipografía mono) sin rediseñar el componente.
5. WHEN se listan 5 o más personas asignadas (sumando las 3 secciones: RRPP, Guardias, Cajeras), THE Sistema SHALL permitir desplazarse por la lista completa mediante scroll vertical interno sin que el layout general de la página se rompa ni se genere scroll horizontal.
6. IF el panel de personal no tiene contenido suficiente para exceder los 320px de altura máxima, THEN THE Sistema SHALL renderizar el panel sin barra de scroll, ajustándose a la altura natural de su contenido.
