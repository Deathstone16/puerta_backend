# Documento de Requisitos — Gestión de Guardias y Cajeras + Validación QR

## Introducción

El dueño debe poder crear cuentas de guardias y cajeras, asignarlas a sus eventos, y que el sistema valide QRs automáticamente según quién esté activo en la noche. Si el dueño solo tiene 1 guardia o 1 cajera, el QR se valida directamente con ese usuario. Además, si tiene cajera, se habilita el panel de "Cierre de Caja" en su dashboard.

---

## Glosario

- **Guardia**: Usuario con rol `guardia` que escanea QRs/DNIs, aprueba o rebota asistentes en la puerta.
- **Cajera**: Usuario con rol `cajera` que cobra a los asistentes aprobados (efectivo/transferencia) y registra el ingreso final.
- **Asignación de staff**: Relación entre un guardia/cajera y un evento específico. Permite que el dueño controle quién trabaja en cada noche.
- **Validación QR automática**: Si solo hay 1 guardia o 1 cajera asignado al evento, el sistema puede resolver automáticamente quién valida sin necesidad de login separado del staff.

---

## Requisitos

### Requisito 1: Crear guardias desde el dashboard del dueño

**Historia de usuario:** Como dueño, quiero crear cuentas de guardia para mi equipo, asignándoles un nombre, usuario y contraseña para que puedan acceder a la app de puerta.

#### Criterios de aceptación

1. THE Sistema SHALL proveer un endpoint `POST /api/staff/` que permita al dueño crear usuarios con rol `guardia` o `cajera`.
2. THE formulario de alta SHALL solicitar: nombre, apellido, username, contraseña, y rol (guardia/cajera). Campos obligatorios marcados con *.
3. THE Sistema SHALL asociar el staff creado al organizador que lo creó (campo `organizador` o similar para filtrar).
4. THE endpoint `GET /api/staff/` SHALL devolver la lista de guardias y cajeras del organizador autenticado.
5. THE endpoint `PATCH /api/staff/:id/` SHALL permitir editar nombre/apellido del staff.
6. THE endpoint `DELETE /api/staff/:id/` SHALL desactivar la cuenta del staff (no eliminar).

### Requisito 2: Crear cajeras desde el dashboard del dueño

**Historia de usuario:** Como dueño, quiero crear cuentas de cajera para mi equipo, para que puedan cobrar en la puerta y registrar ingresos.

#### Criterios de aceptación

1. THE misma interfaz de alta de staff SHALL permitir elegir entre rol "Guardia" y "Cajera".
2. THE lista de staff en el dashboard SHALL mostrar guardias y cajeras juntos, diferenciados por un badge de rol.
3. THE Sistema SHALL aplicar las mismas reglas de creación/edición/eliminación que para guardias.

### Requisito 3: Asignar guardias y cajeras a eventos

**Historia de usuario:** Como dueño, quiero asignar guardias y cajeras específicos a cada evento, para controlar quién trabaja en cada noche.

#### Criterios de aceptación

1. THE Sistema SHALL proveer un modelo `AsignacionStaff` con: staff (FK usuario), evento (FK evento), rol, activa (bool).
2. THE endpoint `POST /api/staff/:id/asignar-evento/` SHALL asignar un guardia/cajera a un evento.
3. THE NochesTab (detalle de evento) SHALL mostrar los guardias y cajeras asignados como píldoras, similar a RRPP.
4. THE Sistema SHALL validar que un evento tenga al menos 1 guardia O 1 cajera asignado antes de poder activar la validación de QR.

### Requisito 4: Validación QR por usuario activo

**Historia de usuario:** Como dueño, quiero que si solo tengo 1 guardia o 1 cajera asignado a un evento, el QR se valide automáticamente con ese usuario sin necesidad de login separado.

#### Criterios de aceptación

1. WHEN un guardia se loguea en la app (`/guardia`), THE Sistema SHALL mostrar solo los eventos a los que está asignado.
2. WHEN solo hay 1 guardia asignado al evento, THE Sistema SHALL auto-seleccionar ese evento al loguearse.
3. WHEN una cajera se loguea en la app (`/cajera`), THE Sistema SHALL mostrar solo los eventos a los que está asignada.
4. THE endpoint de login SHALL incluir en la respuesta el `evento_id` si el staff solo tiene 1 evento asignado activo.

### Requisito 5: Cierre de Caja condicionado a tener cajera

**Historia de usuario:** Como dueño, quiero que el panel "Cierre de Caja" aparezca en mi dashboard solo si tengo al menos una cajera creada, porque si no tiene cajera no necesita ese panel.

#### Criterios de aceptación

1. THE DashboardPage SHALL mostrar la tab "Cierre de Caja" SOLO si el dueño tiene al menos 1 cajera activa en su staff.
2. WHEN el dueño no tiene cajeras, THE Sistema SHALL mostrar solo las tabs: Métricas, Noches, Mis RRPP, Auditoría RRPP.
3. WHEN el dueño tiene al menos 1 cajera, THE Sistema SHALL agregar la tab "Cierre de Caja" dinámicamente.

### Requisito 6: Panel "Mi Staff" en el dashboard del dueño

**Historia de usuario:** Como dueño, quiero tener una tab donde veo todos mis guardias y cajeras, pueda crearlos, editarlos y eliminarlos.

#### Criterios de aceptación

1. THE DashboardPage SHALL tener una tab "Mi Staff" que muestre la lista de guardias y cajeras del dueño.
2. THE tab SHALL mostrar: nombre, username, rol (badge), eventos asignados (count), y botones de editar/eliminar.
3. THE tab SHALL tener un botón "Crear Staff" que abre un modal de alta.
4. THE modal de alta SHALL pedir: nombre *, apellido *, username *, contraseña *, rol (guardia/cajera) *. Sin teléfono obligatorio.
