# Documento de Diseño — Comisión RRPP por evento + Fix panel RRPP

## Cambio de modelo de datos

### Antes (actual):
```
RRPP
├── tipo_comision: CharField (fijo/porcentaje)  ← global
├── valor_comision: DecimalField               ← global
└── asignaciones → AsignacionRRPP
    ├── rrpp: FK
    ├── evento: FK
    └── activa: bool
```

### Después (propuesto):
```
RRPP
├── tipo_comision: CharField (nullable, default)  ← opcional, solo como sugerencia
├── valor_comision: DecimalField (nullable)       ← opcional, solo como sugerencia
└── asignaciones → AsignacionRRPP
    ├── rrpp: FK
    ├── evento: FK
    ├── activa: bool
    ├── tipo_comision: CharField (fijo/porcentaje)  ← POR EVENTO
    └── valor_comision: DecimalField                ← POR EVENTO
```

La comisión se define a nivel de asignación, no a nivel de RRPP. Los campos en el modelo RRPP se hacen nullable/opcionales como sugerencia de valores default.

## Migración

1. Agregar `tipo_comision` y `valor_comision` a `AsignacionRRPP`
2. Copiar los valores actuales de `RRPP.tipo_comision` / `RRPP.valor_comision` a las asignaciones existentes
3. Hacer nullable los campos en `RRPP`

## Flujo de asignación (actualizado)

1. Dueño abre panel de RRPP de un evento (botón 👥 en la tab Noches)
2. Escribe nombre del RRPP en el autocomplete
3. Selecciona un RRPP → se muestra un mini-form pidiendo tipo y valor de comisión
4. Confirma → `POST /api/rrpp/:id/asignar-evento/` con `{evento_id, tipo_comision, valor_comision}`
5. Backend crea la asignación con esos valores
6. Frontend muestra "RRPP asignado con éxito al evento X" (no links)

## Fix del polling en panel RRPP

**Problema:** El panel RRPP pollea cada 4 segundos. Cada request envía el JWT. Si el token expira entre polls y el refresh falla (por race condition o timing), el `ProtectedRoute` detecta `isAuthenticated = false` y redirige a `/login`.

**Solución:**
- Aumentar el intervalo de polling a 15 segundos
- En el `catch` del polling, si el error es 401, no setear `panelStatus = 'error'` (dejar que el AuthContext maneje el refresh silenciosamente)
- El AuthContext ya intenta refresh automático en `apiRequest` cuando recibe 401

## Respuesta del endpoint de asignación (simplificada)

```json
// POST /api/rrpp/:id/asignar-evento/
// Request: { "evento_id": 5, "tipo_comision": "fijo", "valor_comision": 1500 }
// Response 201:
{
  "asignacion_id": 12,
  "rrpp_nombre": "Lucía Fernández",
  "evento_nombre": "NEON PROTOCOL",
  "tipo_comision": "fijo",
  "valor_comision": 1500
}
```

El frontend ya NO recibe ni muestra `links` — esos se generan internamente para uso del RRPP.

## Cálculo de pago por RRPP en ranking

En `GET /api/dashboard/ranking-rrpp/:evento_id/`:
- `comision_a_pagar` se calcula usando `asignacion.tipo_comision` y `asignacion.valor_comision` (no los del modelo RRPP global)
- Los campos `tipo_comision` y `valor_comision` de la asignación se incluyen en la respuesta
