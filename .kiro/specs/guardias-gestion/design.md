# Documento de Diseño — Gestión de Guardias y Cajeras

## Modelo de datos

### Nuevo modelo: AsignacionStaff

```python
class AsignacionStaff(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='asignaciones_staff')
    evento = models.ForeignKey('eventos.Evento', on_delete=models.CASCADE, related_name='staff_asignado')
    rol = models.CharField(max_length=20, choices=[('guardia', 'Guardia'), ('cajera', 'Cajera')])
    activa = models.BooleanField(default=True)

    class Meta:
        unique_together = ('usuario', 'evento')
```

No se crea un modelo separado tipo "Guardia" o "Cajera" — se usa directamente el modelo `Usuario` con `rol='guardia'` o `rol='cajera'`. La asignación al evento se maneja con `AsignacionStaff`.

### Relación con el organizador

El `Usuario` de staff (guardia/cajera) no tiene un campo `organizador` directo. En vez de eso:
- Al crear el staff, el endpoint verifica `IsDueno` y filtra por los usuarios que ese dueño creó.
- Se usa un approach similar al de RRPP: el dueño lista solo los staff cuyos `AsignacionStaff.evento.organizador == request.user`, o un campo `created_by` en el usuario.

**Decisión:** Agregar campo `created_by` al modelo `Usuario` (nullable FK a sí mismo) para poder filtrar staff por quién los creó. Alternativamente, crear una tabla `StaffDelOrganizador` similar a `RRPP.organizador`. 

**Approach elegido:** Usar la misma lógica que RRPP — crear un endpoint `GET /api/staff/` que filtra usuarios con `rol__in=['guardia', 'cajera']` que fueron creados por el request.user. Para esto, agregamos un campo genérico al usuario o usamos un modelo intermedio.

**Simplificación para MVP:** Agregar `organizador` FK nullable al modelo `Usuario`. Al crear staff, se setea `organizador = request.user`. Para listar se filtra por organizador.

## Endpoints

| Método | Path | Descripción |
|--------|------|-------------|
| GET | /api/staff/ | Lista guardias y cajeras del organizador |
| POST | /api/staff/ | Crear guardia o cajera |
| PATCH | /api/staff/:id/ | Editar nombre/apellido |
| DELETE | /api/staff/:id/ | Desactivar staff |
| POST | /api/staff/:id/asignar-evento/ | Asignar staff a evento |
| GET | /api/staff/:id/asignar-evento/ | Eventos disponibles para asignar |

## Frontend

### Tab "Mi Staff" en DashboardPage
- Similar a GestionRrppTab: tabla con nombre, username, rol (badge), eventos (count), acciones
- Botón "Crear Staff" abre modal con campos: nombre, apellido, username, contraseña, rol
- Edición inline de nombre/apellido
- Eliminar con confirmación

### Asignación de staff a eventos (en NochesTab)
- Al expandir un evento, además de la sección de RRPP, mostrar sección de "Staff asignado"
- Píldoras de guardias (azul) y cajeras (cyan) con autocomplete para agregar

### Tab "Cierre de Caja" condicional
- En DashboardPage: al cargar, verificar si el dueño tiene cajeras (del endpoint /api/staff/ o del campo en boliche)
- Si tiene: agregar tab dinámicamente
- Si no: no mostrar

## Validación QR automática

Cuando el guardia se loguea:
1. El endpoint de login devuelve `evento_id` si el guardia tiene exactamente 1 asignación activa
2. El frontend de GuardPage usa ese `evento_id` para filtrar los asistentes
3. Si tiene múltiples eventos, muestra un selector de evento al inicio

Lo mismo para la cajera.

## Migración

1. Agregar campo `organizador` (FK, nullable) al modelo `Usuario` (solo para staff)
2. Crear modelo `AsignacionStaff` en la app `puerta` o crear una nueva app `staff`
3. Crear vistas y URLs

**Decisión de app:** Poner todo en una nueva app `staff` para mantener separación. Alternativamente, ponerlo en `cuentas` ya que extiende el modelo de usuario.

**Approach final:** Ponerlo en `apps.cuentas` ya que el modelo Usuario vive ahí, y crear las vistas de gestión ahí mismo.
