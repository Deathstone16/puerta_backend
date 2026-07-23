# Documento de Requisitos — Comisión RRPP por evento + Fix panel RRPP

## Introducción

Este spec aborda 4 problemas relacionados:
1. La comisión del RRPP debe definirse al asignar al evento, no al crear la cuenta
2. El panel RRPP redirige al login después de pocos segundos (sesión expira)
3. El panel RRPP no muestra los eventos asignados correctamente
4. Al asignar un RRPP, el frontend muestra "links" generados en vez de un mensaje de éxito simple

---

## Glosario

- **RRPP**: Relaciones públicas — persona que gestiona listas de invitados
- **Asignación**: Relación entre un RRPP y un evento específico
- **Comisión por evento**: Monto/porcentaje que cobra el RRPP por cada ingresado en un evento específico
- **Panel RRPP**: Vista `/rrpp` donde el RRPP ve sus eventos, lista de invitados, etc.
- **Dueño**: Organizador que crea RRPP y los asigna a eventos

---

## Requisitos

### Requisito 1: Comisión definida por evento (no por cuenta)

**Historia de usuario:** Como dueño, quiero definir cuánto cobra cada RRPP en cada evento al que lo asigno, porque el mismo RRPP puede cobrar diferente según la noche.

#### Criterios de aceptación

1. THE modelo `AsignacionRRPP` SHALL tener campos `tipo_comision` (fijo/porcentaje) y `valor_comision` (decimal) propios de la asignación.
2. WHEN el dueño asigna un RRPP a un evento, THE Sistema SHALL requerir que se indique el tipo y valor de comisión para esa asignación específica.
3. THE modelo `RRPP` SHALL dejar de tener los campos `tipo_comision` y `valor_comision` como obligatorios — se pueden mantener como "default" o eliminarse.
4. WHEN el dueño ve la información de un evento, THE Sistema SHALL mostrar cuánto le tiene que pagar a cada RRPP asignado, calculado como: `valor_comision × ingresados` (si fijo) o `recaudación × valor_comision / 100` (si porcentaje).
5. THE API `POST /api/rrpp/:id/asignar-evento/` SHALL aceptar `tipo_comision` y `valor_comision` en el body junto con `evento_id`.

### Requisito 2: Crear RRPP sin comisión obligatoria

**Historia de usuario:** Como dueño, quiero crear cuentas de RRPP sin definir comisión al crearlas, porque la comisión la defino cuando asigno al evento.

#### Criterios de aceptación

1. THE endpoint `POST /api/rrpp/` SHALL hacer opcionales los campos `tipo_comision` y `valor_comision` al crear un RRPP.
2. THE frontend de "Alta RRPP" SHALL no mostrar campos de comisión (se eliminan del formulario de creación).
3. THE lista de "Mis RRPP" en el dashboard del dueño SHALL no mostrar columna de comisión global.

### Requisito 3: Mensaje de éxito al asignar RRPP

**Historia de usuario:** Como dueño, quiero ver un mensaje simple "RRPP asignado con éxito" cuando asigno un RRPP a un evento, en vez de ver links técnicos.

#### Criterios de aceptación

1. WHEN la asignación es exitosa, THE frontend SHALL mostrar "RRPP asignado con éxito al evento [nombre]" en vez de mostrar los links generados.
2. THE frontend SHALL cerrar el panel de asignación automáticamente después de 2 segundos, o al presionar un botón "Listo".

### Requisito 4: Fix del panel RRPP — Sesión expira rápido

**Historia de usuario:** Como RRPP, quiero que mi sesión dure el tiempo esperado sin que me redirija al login después de pocos segundos.

#### Criterios de aceptación

1. THE panel RRPP (`/rrpp`) SHALL mantener la sesión activa mientras el usuario esté en la página.
2. WHEN el polling de `/rrpp/mi-panel/` recibe un 401, THE Sistema SHALL intentar refrescar el token antes de redirigir al login.
3. THE intervalo de polling SHALL ser 15 segundos (no 4 segundos) para reducir la carga de requests y las chances de race condition con el token refresh.
4. WHEN el RRPP tiene eventos asignados, THE panel SHALL mostrar cada evento con su información correcta (nombre, fecha, estadísticas).

### Requisito 5: Comisión visible al seleccionar evento en el dashboard del dueño

**Historia de usuario:** Como dueño, quiero ver en el detalle de cada evento cuánto tengo que pagar a cada RRPP asignado según sus ingresados.

#### Criterios de aceptación

1. WHEN el dueño expande el panel de RRPP de un evento (en la tab Noches), THE Sistema SHALL mostrar junto a cada píldora de RRPP asignado: su tipo de comisión, valor, y el monto a pagar basado en los ingresados de esa noche.
2. THE endpoint `GET /api/dashboard/ranking-rrpp/:evento_id/` SHALL incluir los campos `tipo_comision` y `valor_comision` de la asignación (no del modelo RRPP global).
