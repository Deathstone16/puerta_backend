# Plan de implementación — Gestión de Guardias y Cajeras

## Resumen

Permitir al dueño crear guardias y cajeras, asignarlas a eventos, con validación QR automática y panel de cierre de caja condicional.

**Prerequisitos:**
- Modelo `Usuario` con campo `rol` (ya existe)
- App `cuentas` con permisos (ya existe)
- GuardPage y CashierPage ya funcionales en frontend

---

## Tareas

- [ ] 1. Agregar campo `organizador` al modelo Usuario + migración
  - En `apps/cuentas/models.py`: agregar `organizador = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='staff_creado')`
  - Crear migración
  - _Requisito 1.3_

- [ ] 2. Crear modelo AsignacionStaff + migración
  - En `apps/cuentas/models.py` (o nueva app):
    ```python
    class AsignacionStaff(models.Model):
        usuario = FK(Usuario, CASCADE, related_name='asignaciones_staff')
        evento = FK('eventos.Evento', CASCADE, related_name='staff_asignado')
        rol = CharField(max_length=20, choices=[('guardia','Guardia'),('cajera','Cajera')])
        activa = BooleanField(default=True)
        class Meta:
            unique_together = ('usuario', 'evento')
    ```
  - Crear migración
  - _Requisito 3.1_

- [ ] 3. Crear endpoints CRUD de staff
  - `StaffListCreateView` en `apps/cuentas/views.py`:
    - GET: `Usuario.objects.filter(organizador=request.user, rol__in=['guardia','cajera'], is_active=True)`
    - POST: crear usuario con rol guardia/cajera, setear `organizador=request.user`
  - `StaffDetailView`:
    - PATCH: editar nombre/apellido
    - DELETE: desactivar `is_active=False`
  - URLs: `/api/staff/`, `/api/staff/:id/`
  - _Requisitos 1.1–1.6, 2.1–2.3_

- [ ] 4. Crear endpoint de asignación de staff a evento
  - `StaffAsignarEventoView`:
    - POST `/api/staff/:id/asignar-evento/`: crea AsignacionStaff
    - GET `/api/staff/:id/asignar-evento/`: eventos disponibles
  - Validar que el evento pertenece al organizador
  - Si ya está asignado activo: devolver 200 sin error
  - _Requisito 3.2_

- [ ] 5. Actualizar login para incluir evento_id del staff
  - En el endpoint de login (`/api/auth/login/`): si el usuario tiene rol guardia o cajera, buscar su asignación activa
  - Si tiene exactamente 1: incluir `evento_id` en la respuesta
  - Si tiene >1: incluir lista de `eventos_asignados`
  - _Requisito 4.1–4.4_

- [ ] 6. Frontend: Crear tab "Mi Staff" en dashboard
  - Nuevo componente `GestionStaffTab.jsx` similar a `GestionRrppTab.jsx`
  - Tabla: nombre, username, rol (badge guardia=azul/cajera=cyan), eventos asignados, acciones
  - Botón "Crear Staff" → modal con campos nombre*, apellido*, username*, contraseña*, rol*
  - Edición inline nombre/apellido
  - Eliminar con confirmación
  - _Requisito 6.1–6.4_

- [ ] 7. Frontend: Modal StaffFormModal
  - Campos: nombre*, apellido*, username*, contraseña*, rol (select: Guardia/Cajera)*
  - Similar a RrppFormModal pero con selector de rol
  - _Requisito 1.2, 2.1_

- [ ] 8. Frontend: Asignación de staff a eventos (en NochesTab)
  - Agregar sección "Staff asignado" debajo de la sección RRPP en el panel expandible de cada evento
  - Nuevo componente `EventoStaffAssigner.jsx`:
    - Píldoras de guardias (azul) y cajeras (cyan) ya asignados
    - Autocomplete para agregar staff disponible
    - Al seleccionar, asigna directamente (no necesita comisión)
  - _Requisito 3.3_

- [ ] 9. Frontend: Tab "Cierre de Caja" condicional
  - En DashboardPage: al cargar staff, verificar si hay al menos 1 cajera activa
  - Si sí: agregar tab "Cierre de Caja" al array TABS dinámicamente
  - Importar `CierreCajaTab` (ya existe) y renderizar condicionalmente
  - _Requisito 5.1–5.3_

- [ ] 10. Frontend: GuardPage usa evento asignado del login
  - Si `session.evento_id` existe: usar ese evento automáticamente
  - Si `session.eventos_asignados` tiene >1: mostrar selector de evento al inicio
  - Si no tiene asignaciones: mostrar mensaje "No tenés eventos asignados"
  - _Requisito 4.1–4.3_

- [ ] 11. Frontend: CashierPage usa evento asignado del login
  - Misma lógica que GuardPage
  - _Requisito 4.3_

- [ ] 12. Agregar DashboardPage tabs dinámicas
  - Agregar tab "Mi Staff" siempre visible
  - Agregar tab "Cierre de Caja" solo si tiene cajeras
  - TABS array final: Métricas, Noches, Mis RRPP, Mi Staff, Auditoría RRPP, [Cierre de Caja]
  - _Requisitos 5.1–5.3, 6.1_

- [ ] 13. Verificación final
  - Dueño puede crear guardia y cajera
  - Dueño puede asignar staff a eventos
  - Guardia ve solo sus eventos asignados
  - Cajera ve solo sus eventos asignados
  - Tab "Cierre de Caja" aparece solo si hay cajera
  - Backend: `python manage.py check` sin errores
  - Migraciones aplicadas correctamente

---

## Notas

- El guardia y la cajera NO necesitan "comisión" como los RRPP — se asignan directamente al evento.
- El modelo `AsignacionStaff` es independiente de `AsignacionRRPP` — son staff operativo, no comercial.
- Si el dueño solo tiene 1 guardia y 1 cajera, puede usar la validación QR simplificada donde esos usuarios se auto-asignan al único evento activo.
- El campo `organizador` en Usuario es nullable porque solo aplica a staff (no a dueños ni superadmins).
- Los endpoints de staff viven en `apps/cuentas/` ya que extienden la gestión de usuarios.
