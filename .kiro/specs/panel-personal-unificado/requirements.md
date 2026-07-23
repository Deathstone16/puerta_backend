# Documento de Requisitos — Panel "Mi Personal" unificado

## Introducción

Actualmente el dueño tiene dos tabs separadas para gestionar su equipo: "Mis RRPP" y "Mi Staff" (guardias/cajeras). Esto se unifica en una sola tab "Mi Personal" donde el dueño da de alta a todo su equipo (RRPP, Guardia, Cajera) desde un único panel, los asigna a eventos, y ve al expandir cada evento qué personal tiene asignado con sus roles.

---

## Glosario

- **Personal**: Cualquier usuario creado por el dueño — incluye RRPP, Guardias y Cajeras.
- **Asignación**: Relación entre un miembro del personal y un evento.
- **Panel expandido del evento**: Al hacer click en el ícono de personas de un evento en "Noches", se despliega un panel que muestra todo el personal asignado agrupado por rol.

---

## Requisitos

### Requisito 1: Tab única "Mi Personal" reemplaza "Mis RRPP" y "Mi Staff"

**Historia de usuario:** Como dueño, quiero gestionar todo mi equipo desde un solo lugar, sin tener que ir a tabs separadas para RRPP y guardias/cajeras.

#### Criterios de aceptación

1. THE DashboardPage SHALL mostrar UNA sola tab "Mi Personal" en vez de "Mis RRPP" y "Mi Staff" separadas.
2. THE tab "Mi Personal" SHALL mostrar una tabla con TODO el personal del dueño: RRPP, Guardias y Cajeras juntos.
3. THE tabla SHALL mostrar columnas: Nombre, Usuario, Rol (badge con color), Eventos asignados, Acciones (editar/eliminar).
4. THE tabla SHALL diferenciar visualmente cada rol: RRPP = violeta/strobe, Guardia = azul/cyan, Cajera = verde/emerald.

### Requisito 2: Crear personal de cualquier rol desde el mismo formulario

**Historia de usuario:** Como dueño, quiero crear RRPP, guardias y cajeras desde el mismo botón "Crear Personal", eligiendo el rol al momento de dar de alta.

#### Criterios de aceptación

1. THE formulario de alta SHALL tener un selector de rol con 3 opciones: RRPP, Guardia, Cajera.
2. THE formulario SHALL solicitar: nombre *, apellido *, username *, contraseña *, rol *.
3. WHEN el rol es "RRPP", THE Sistema SHALL crear el usuario con rol RRPP y crear el registro en el modelo RRPP (asociado al organizador).
4. WHEN el rol es "guardia" o "cajera", THE Sistema SHALL crear el usuario con ese rol y setear el organizador.
5. THE formulario SHALL NO pedir comisión (se define al asignar RRPP a un evento).

### Requisito 3: Asignar personal a eventos desde la tab "Mi Personal"

**Historia de usuario:** Como dueño, quiero poder asignar cualquier miembro de mi personal a un evento directamente desde la lista de personal.

#### Criterios de aceptación

1. THE tab "Mi Personal" SHALL tener un botón "Asignar a evento" que abre un modal donde selecciono persona + evento.
2. WHEN asigno un RRPP a un evento, THE Sistema SHALL pedir la comisión (tipo + valor) como ya funciona.
3. WHEN asigno un guardia o cajera a un evento, THE Sistema SHALL asignar directamente sin pedir comisión.

### Requisito 4: Evento expandido muestra todo el personal asignado

**Historia de usuario:** Como dueño, quiero que al expandir un evento en la tab "Noches", vea todo el personal asignado organizado por rol.

#### Criterios de aceptación

1. WHEN expando un evento, THE panel SHALL mostrar 3 secciones: RRPP, Guardias, Cajeras.
2. Cada sección SHALL mostrar píldoras con el nombre del personal asignado y su rol (color-coded).
3. RRPP asignados SHALL mostrar además la comisión configurada (ej: "$1500/ingresado").
4. Cada sección SHALL tener un input de autocompletado para agregar más personal de ese rol.
5. THE panel SHALL permitir quitar personal asignado con un botón X en la píldora.

### Requisito 5: Endpoint unificado de personal

**Historia de usuario:** Como frontend, necesito un solo endpoint que me devuelva todo el personal del dueño (RRPP + guardias + cajeras) para simplificar la UI.

#### Criterios de aceptación

1. THE endpoint `GET /api/personal/` SHALL devolver todos los usuarios creados por el dueño, incluyendo RRPP, guardias y cajeras.
2. THE respuesta SHALL incluir para cada uno: id, nombre, username, rol, eventos asignados (count y lista).
3. THE endpoint `POST /api/personal/` SHALL crear personal de cualquier rol (rrpp, guardia, cajera).
4. THE endpoint `DELETE /api/personal/:id/` SHALL desactivar al usuario.
5. THE endpoint `POST /api/personal/:id/asignar-evento/` SHALL asignar a un evento (con comisión si es RRPP, sin si es guardia/cajera).
