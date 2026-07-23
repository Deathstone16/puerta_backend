# Plan de implementación — Comisión RRPP por evento + Fix panel RRPP

## Resumen

Mover la comisión del modelo RRPP al modelo AsignacionRRPP (por evento), simplificar el flujo de asignación en el frontend, y arreglar el panel RRPP que expira la sesión rápido.

**Prerequisitos:** Ninguno. Los cambios son sobre código existente.

---

## Tareas

- [ ] 1. Migración: agregar campos de comisión a AsignacionRRPP
  - Agregar a `AsignacionRRPP` en `api/apps/rrpp/models.py`:
    - `tipo_comision = CharField(max_length=20, choices=RRPP.TIPO_COMISION, default='fijo')`
    - `valor_comision = DecimalField(max_digits=10, decimal_places=2, default=0)`
  - Hacer nullable los campos en `RRPP`:
    - `tipo_comision` → `blank=True, null=True`
    - `valor_comision` → `blank=True, null=True`
  - Crear migración: `python manage.py makemigrations rrpp`
  - En la migración, agregar data migration que copie `rrpp.tipo_comision` y `rrpp.valor_comision` a cada `AsignacionRRPP` existente
  - Aplicar: `python manage.py migrate`
  - _Requisito 1.1, 1.3_

- [ ] 2. Actualizar endpoint POST /api/rrpp/:id/asignar-evento/
  - Aceptar `tipo_comision` y `valor_comision` en el request body (obligatorios)
  - Crear AsignacionRRPP con esos valores: `AsignacionRRPP.objects.create(rrpp=rrpp, evento=evento, tipo_comision=..., valor_comision=...)`
  - Cambiar la respuesta de éxito: devolver `{asignacion_id, rrpp_nombre, evento_nombre, tipo_comision, valor_comision}` — NO devolver `links`
  - _Requisitos 1.2, 1.5, 3.1_

- [ ] 3. Actualizar creación de RRPP — hacer comisión opcional
  - En `RRPPCreateSerializer` (`api/apps/rrpp/serializers.py`): hacer `tipo_comision` y `valor_comision` opcionales (`required=False`, con defaults)
  - En el frontend `RrppFormModal.jsx`: eliminar los campos de comisión del formulario de alta
  - En `GestionRrppTab.jsx`: eliminar la columna "Comisión" de la tabla
  - _Requisito 2.1, 2.2, 2.3_

- [ ] 4. Actualizar EventoRrppAssigner — pedir comisión al asignar
  - Cuando el usuario selecciona un RRPP del autocomplete, NO asignar inmediatamente
  - Mostrar un mini-form inline con: select tipo (Fijo / Porcentaje) + input valor
  - Al confirmar, hacer el POST con `{evento_id, tipo_comision, valor_comision}`
  - Al recibir éxito: mostrar mensaje "RRPP asignado con éxito al evento [nombre]" durante 2s, luego agregar la píldora
  - NO mostrar links en ningún momento
  - _Requisitos 1.2, 3.1, 3.2_

- [ ] 5. Mostrar comisión a pagar en el detalle de RRPP por evento
  - En `EventoRrppAssigner`: junto a cada píldora de RRPP asignado, mostrar el tipo y valor de comisión
  - Para obtener esta info, el endpoint `GET /api/rrpp/` ya devuelve asignaciones — agregar `tipo_comision` y `valor_comision` al serializer de `AsignacionConEstadisticasSerializer`
  - En el ranking (`/dashboard/ranking-rrpp/:id/`): usar `asignacion.tipo_comision` y `asignacion.valor_comision` para el cálculo de `comision_a_pagar`
  - _Requisitos 5.1, 5.2_

- [ ] 6. Fix panel RRPP — sesión expira
  - En `RrppPage.jsx`: cambiar intervalo de polling de 4000ms a 15000ms
  - En el `catch` del `loadPanel`: si el error tiene status 401, NO setear `panelStatus = 'error'` — dejar que el refresh del AuthContext actúe
  - Verificar que `MiPanelView` en el backend devuelve los eventos asignados correctamente (con nombre, fecha, estadísticas)
  - _Requisitos 4.1, 4.2, 4.3, 4.4_

- [ ] 7. Verificación final
  - Panel RRPP mantiene sesión estable (no redirige al login)
  - Panel RRPP muestra eventos asignados con info correcta
  - Asignación de RRPP pide comisión y muestra "asignado con éxito"
  - Dashboard del dueño muestra pago a RRPP por evento
  - Creación de RRPP no pide comisión
  - Backend: `python manage.py check` sin errores
  - Migración aplicada correctamente

---

## Notas

- Los links RRPP se siguen generando internamente (los necesita el panel del RRPP para compartir su link de lista), pero ya no se muestran al dueño en el momento de asignar.
- Si un RRPP tiene asignaciones existentes sin comisión (de antes de la migración), la data migration les copia los valores del modelo RRPP para mantener consistencia.
- El cambio de polling de 4s a 15s reduce la carga sobre la API y baja la probabilidad de race conditions con el token refresh.
