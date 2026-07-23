# Plan de implementación — Comisión RRPP por evento + Fix panel RRPP

## Resumen

Mover la comisión del modelo RRPP al modelo AsignacionRRPP (por evento), simplificar el flujo de asignación en el frontend, y arreglar el panel RRPP que expira la sesión rápido.

**Prerequisitos:** Ninguno. Los cambios son sobre código existente.

---

## Tareas

- [x] 1. Migración: agregar campos de comisión a AsignacionRRPP
  - Agregado `tipo_comision` y `valor_comision` a `AsignacionRRPP` con defaults
  - Hecho nullable `tipo_comision` y `valor_comision` en modelo `RRPP`
  - Creada migración `0003_comision_por_evento.py` con data migration
  - _Requisito 1.1, 1.3_

- [x] 2. Actualizar endpoint POST /api/rrpp/:id/asignar-evento/
  - Acepta `tipo_comision` y `valor_comision` (obligatorios)
  - Crea AsignacionRRPP con esos valores
  - Respuesta simplificada: `{asignacion_id, rrpp_nombre, evento_nombre, tipo_comision, valor_comision}`
  - Si RRPP ya asignado activo: devuelve 200 con `ya_asignado: true` (no error)
  - Si hay asignación inactiva: la reactiva con nueva comisión
  - _Requisitos 1.2, 1.5, 3.1_

- [x] 3. Actualizar creación de RRPP — hacer comisión opcional
  - `RRPPCreateSerializer`: `tipo_comision` y `valor_comision` opcionales con `required=False`
  - `RrppFormModal.jsx`: eliminados campos de comisión, campos obligatorios marcados con *, teléfono marcado como (opcional)
  - `GestionRrppTab.jsx`: eliminada columna "Comisión" de la tabla
  - _Requisito 2.1, 2.2, 2.3_

- [x] 4. Actualizar EventoRrppAssigner — pedir comisión al asignar
  - Al seleccionar RRPP: muestra mini-form con tipo + valor de comisión (marcado como obligatorio *)
  - Al confirmar: POST con `{evento_id, tipo_comision, valor_comision}`
  - Éxito: muestra "RRPP asignado con éxito a [evento]" durante 3s
  - Error: muestra detalle del error en alert
  - Después de asignar: recarga datos con `loadData()`
  - Píldoras muestran comisión ($ o %) junto al nombre
  - _Requisitos 1.2, 3.1, 3.2, 5.1_

- [x] 5. Actualizar AsignarRrppModal (modal separado)
  - Agregados campos tipo comisión + valor comisión (obligatorios con *)
  - Envía `tipo_comision` y `valor_comision` al endpoint
  - Muestra "RRPP asignado con éxito" en vez de links
  - Al cerrar: dispara refresh de listas en el padre
  - _Requisitos 1.2, 3.1_

- [x] 6. Serializers y ranking — comisión desde AsignacionRRPP
  - `AsignacionConEstadisticasSerializer`: incluye `tipo_comision` y `valor_comision`
  - `RankingRRPPView`: calcula comisión usando `asig.tipo_comision` y `asig.valor_comision`
  - _Requisitos 5.1, 5.2_

- [x] 7. Fix panel RRPP — sesión expira
  - Polling cambiado de 4s a 15s
  - Error 401 se ignora silenciosamente (AuthContext maneja el refresh)
  - _Requisitos 4.1, 4.2, 4.3_

- [x] 8. Persistencia de sesión
  - Sesión guardada en `sessionStorage` (sobrevive recargas, se borra al cerrar pestaña)
  - Al cargar: lee sesión guardada y verifica que no esté expirada
  - Al logout: limpia sessionStorage
  - _Requisito 4.1_

- [x] 9. Refresh automático de listas después de mutaciones
  - `DashboardPage` usa `refreshKey` counter que se incrementa en cada mutación
  - `GestionRrppTab` recibe `key={refreshKey}` para re-montarse al cambiar
  - `RrppFormModal` llama `triggerRefresh` al crear exitosamente
  - `AsignarRrppModal` llama `triggerRefresh` al cerrar
  - `EventoRrppAssigner` llama `loadData()` después de asignar
  - _Requisito: listas actualizadas en tiempo real sin recargar_

- [x] 10. Fixes adicionales
  - Dashboard filtra eventos con `?mis_eventos=true` (solo los del dueño)
  - Backend `EventoListView` soporta parámetro `mis_eventos` para filtrar por organizador
  - Favicon SVG con la P de Puerta + título "Puerta" en index.html
  - AsignarRrppModal filtra eventos con `estado !== 'cancelado'` (no `=== 'publicado'`)
  - _Fix de bugs reportados_

---

## Notas

- Los links RRPP se siguen generando internamente pero ya no se muestran al dueño.
- La comisión global en el modelo RRPP queda como nullable (legacy, no se usa más).
- El cambio de polling reduce la carga sobre la API y la probabilidad de race conditions.
- `sessionStorage` fue elegido sobre `localStorage` por seguridad (se limpia al cerrar pestaña).
