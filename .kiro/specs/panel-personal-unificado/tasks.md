# Plan de implementación — Panel "Mi Personal" unificado

## Resumen

Unificar las tabs "Mis RRPP" y "Mi Staff" en una sola tab "Mi Personal". Crear un endpoint backend unificado que devuelva todo el personal. Actualizar el panel expandido de eventos para mostrar RRPP + Guardias + Cajeras juntos.

---

## Tareas

- [x] 1. Backend: Crear endpoint unificado GET/POST /api/personal/
  - Nuevo view `PersonalListCreateView`:
    - GET: busca en Usuario todos los que tengan `organizador=request.user` y `is_active=True`, OR busca en RRPP los que tengan `organizador=request.user`
    - Para RRPP: obtener datos del modelo RRPP (asignaciones con comisión)
    - Para guardias/cajeras: obtener datos de AsignacionStaff
    - Respuesta unificada: `[{id, nombre, username, rol, eventos_asignados, eventos: [{id, nombre, comision?}]}]`
  - POST: según el rol recibido, crear RRPP (con modelo RRPP) o guardia/cajera (con campo organizador)
  - URLs: registrar en config/urls.py como `/api/personal/`

- [x] 2. Backend: Crear endpoint POST /api/personal/:id/asignar-evento/
  - Si el personal es RRPP: requiere tipo_comision + valor_comision, crea AsignacionRRPP
  - Si el personal es guardia/cajera: NO requiere comisión, crea AsignacionStaff
  - Validar que el evento pertenece al organizador
  - Si ya está asignado activo: devolver 200 sin error

- [x] 3. Backend: Crear endpoint DELETE /api/personal/:id/
  - Desactivar usuario (is_active=False)
  - Desactivar asignaciones (RRPP o Staff según rol)

- [x] 4. Frontend: Crear componente GestionPersonalTab.jsx
  - Reemplaza GestionRrppTab y GestionStaffTab
  - Tabla unificada con: nombre, username, rol (badge violeta/cyan/verde), eventos, acciones
  - Botón "Crear Personal" abre modal unificado
  - Botón "Asignar a evento" abre modal de asignación
  - Edición inline de nombre/apellido
  - Eliminar con confirmación

- [x] 5. Frontend: Crear PersonalFormModal.jsx
  - Campos: nombre*, apellido*, username*, contraseña*, rol* (RRPP / Guardia / Cajera)
  - Reemplaza RrppFormModal y StaffFormModal

- [x] 6. Frontend: Actualizar panel expandido del evento en NochesTab
  - Reemplazar EventoRrppAssigner + EventoStaffAssigner por un solo componente EventoPersonalPanel
  - Muestra 3 secciones: RRPP (con comisión), Guardias, Cajeras
  - Cada sección con píldoras + autocompletado para agregar
  - Al agregar RRPP: muestra mini-form de comisión antes de confirmar
  - Al agregar guardia/cajera: asigna directo

- [x] 7. Frontend: Actualizar DashboardPage
  - Quitar tabs "Mis RRPP" y "Mi Staff"
  - Agregar tab "Mi Personal"
  - Quitar imports de GestionRrppTab y GestionStaffTab
  - Importar GestionPersonalTab
  - Quitar RrppFormModal y StaffFormModal de los modales
  - Agregar PersonalFormModal

- [x] 8. Frontend: Actualizar modal de asignación
  - El AsignarRrppModal se reemplaza por un AsignarPersonalModal
  - Selector de personal (muestra todos los roles)
  - Selector de evento
  - Si el personal seleccionado es RRPP: muestra campos de comisión
  - Si es guardia/cajera: no muestra comisión, asigna directo

- [x] 9. Limpieza: Eliminar archivos obsoletos
  - Eliminar GestionRrppTab.jsx (reemplazado por GestionPersonalTab)
  - Eliminar GestionStaffTab.jsx (reemplazado por GestionPersonalTab)
  - Mantener EventoRrppAssigner.jsx y EventoStaffAssigner.jsx como referencia o eliminar si se reemplazaron

- [x] 10. Verificación final
  - Dueño puede crear RRPP, guardia y cajera desde "Mi Personal"
  - La tabla muestra los 3 roles con badges de color
  - Al expandir evento: muestra personal asignado agrupado por rol
  - Asignar RRPP pide comisión, guardia/cajera no
  - Tab "Cierre de Caja" sigue apareciendo solo si hay cajera
  - Endpoints antiguos (/api/rrpp/, /api/staff/) siguen funcionando para no romper el panel RRPP ni el panel Guardia/Cajera
  - Backend: python manage.py check sin errores

---

## Notas

- Los endpoints antiguos (`/api/rrpp/`, `/api/staff/`) NO se eliminan — siguen siendo necesarios para:
  - El panel del RRPP (`/rrpp`) usa `/api/rrpp/mi-panel/`
  - El guardia y cajera necesitan sus endpoints de validación
- El nuevo endpoint `/api/personal/` es una vista del DUEÑO que agrega los datos de ambas fuentes
- El modelo de datos NO cambia — se sigue usando RRPP + AsignacionRRPP para RRPP, y AsignacionStaff para guardias/cajeras
- La diferencia es que el frontend del dueño ahora consume un solo endpoint unificado
