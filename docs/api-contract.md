# Norware — Contrato de API

Este documento es la **fuente de verdad** para todos los endpoints del backend. Cualquier cambio en un endpoint debe actualizarse aquí antes de mergear a `develop`.

**Base URL:** `http://localhost:8000/api` (desarrollo) / `https://api.norware.com/api` (producción)

**Autenticación:** `Authorization: Bearer {access_token}` en el header. Los endpoints marcados como "Público" no requieren token.

---

## Índice

1. [Auth](#1-auth)
2. [Eventos](#2-eventos)
3. [Precios](#3-precios)
4. [RRPP](#4-rrpp)
5. [Lista pública](#5-lista-pública)
6. [Puerta — Guardia](#6-puerta--guardia)
7. [Puerta — Cajera](#7-puerta--cajera)
8. [Dashboard](#8-dashboard)
9. [Pagos y Wallet](#9-pagos-y-wallet)
10. [Admin Norware](#10-admin-norware)

---

## 1. Auth

### `POST /api/auth/login/`

Autentica un usuario y devuelve JWT.

**Auth:** Público

**Request:**
```json
{
  "username": "string",
  "password": "string"
}
```

**Response 200:**
```json
{
  "access":  "eyJ...",
  "refresh": "eyJ...",
  "rol":     "dueno",
  "nombre":  "Carlos García",
  "id":      42
}
```

**Errores:**
- `401` — credenciales incorrectas

---

### `POST /api/auth/refresh/`

Renueva el access token.

**Auth:** Público

**Request:**
```json
{
  "refresh": "eyJ..."
}
```

**Response 200:**
```json
{
  "access": "eyJ..."
}
```

**Errores:**
- `401` — refresh token inválido o expirado

---

## 2. Eventos

### `GET /api/eventos/`

Lista todos los eventos activos (cartelera pública).

**Auth:** Público

**Query params:**
- `estado` (opcional): `activo` | `cancelado` — filtra por estado

**Response 200:**
```json
[
  {
    "id":               1,
    "nombre":           "Noche Techno",
    "fecha":            "2026-08-05T23:00:00-03:00",
    "color_pulsera":    "violeta",
    "precio_base":      5000,
    "precio_publicado": 5700,
    "aforo_max":        800,
    "estado":           "activo",
    "boliche": {
      "id":       1,
      "nombre":   "Club Crobar",
      "direccion":"Av. Figueroa Alcorta 3657, CABA"
    }
  }
]
```

---

### `GET /api/eventos/:id/`

Detalle completo de un evento.

**Auth:** Público

**Response 200:**
```json
{
  "id":               1,
  "nombre":           "Noche Techno",
  "fecha":            "2026-08-05T23:00:00-03:00",
  "aforo_max":        800,
  "color_pulsera":    "violeta",
  "precio_base":      5000,
  "desglose_precio": {
    "precio_base":      5000,
    "fee_mp":           299.5,
    "fee_norware":      400.0,
    "precio_publicado": 5700
  },
  "line_up": [
    { "artista": "DJ Sasha", "horario": "00:00 - 02:00" },
    { "artista": "Miss Monique", "horario": "02:00 - 04:00" }
  ],
  "estado":              "activo",
  "motivo_cancelacion":  null,
  "boliche": {
    "id":       1,
    "nombre":   "Club Crobar",
    "direccion":"Av. Figueroa Alcorta 3657, CABA"
  }
}
```

**Errores:**
- `404` — evento no existe

---

### `POST /api/eventos/`

Crea un nuevo evento.

**Auth:** IsDueno

**Request:**
```json
{
  "boliche_id":    1,
  "nombre":        "Noche Techno",
  "fecha":         "2026-08-05T23:00:00-03:00",
  "aforo_max":     800,
  "color_pulsera": "violeta",
  "precio_base":   5000,
  "line_up": [
    { "artista": "DJ Sasha", "horario": "00:00 - 02:00" }
  ]
}
```

**Response 201:** mismo formato que `GET /api/eventos/:id/`

**Errores:**
- `400` — campos requeridos faltantes o inválidos
- `403` — no es dueño

---

### `PATCH /api/eventos/:id/`

Edita un evento existente. Solo campos enviados se actualizan.

**Auth:** IsDueno (solo el dueño del boliche del evento)

**Request:** cualquier subconjunto de campos del `POST`

**Response 200:** mismo formato que `GET /api/eventos/:id/`

**Errores:**
- `400` — datos inválidos
- `403` — no es el dueño de ese evento
- `404` — evento no existe
- `405` — el evento está cancelado (no se puede editar)

---

### `POST /api/eventos/:id/cancelar/`

Cancela un evento. Dispara reembolsos automáticos de todas las compras web.

**Auth:** IsDueno

**Request:**
```json
{
  "motivo": "El artista principal canceló su actuación"
}
```

**Response 200:**
```json
{
  "id":                 1,
  "estado":             "cancelado",
  "motivo_cancelacion": "El artista principal canceló su actuación",
  "reembolsos_iniciados": 23
}
```

**Errores:**
- `400` — `motivo` vacío o faltante
- `403` — no es el dueño del evento
- `404` — evento no existe
- `409` — el evento ya está cancelado

---

## 3. Precios

### `GET /api/precios/calcular/`

Calcula el precio publicado a partir del precio base. Usado por el frontend para mostrar el desglose en tiempo real mientras el dueño escribe.

**Auth:** Público

**Query params:**
- `precio_base` (requerido): número entero o decimal

**Response 200:**
```json
{
  "precio_base":      5000,
  "fee_mp":           299.5,
  "fee_norware":      400.0,
  "precio_publicado": 5700
}
```

**Errores:**
- `400` — `precio_base` faltante o no numérico

---

## 4. RRPP

### `GET /api/rrpp/`

Lista todos los RRPP del boliche del dueño autenticado.

**Auth:** IsDueno

**Response 200:**
```json
[
  {
    "id":             1,
    "nombre":         "Juan Pérez",
    "username":       "juanperez",
    "tipo_comision":  "fijo",
    "valor_comision": 500.00,
    "asignaciones": [
      {
        "evento_id":   1,
        "evento_nombre": "Noche Techno",
        "activa":      true,
        "links": [
          { "tipo": "lista",     "slug": "a1b2c3d4-...", "url": "/lista/a1b2c3d4-..." },
          { "tipo": "venta_web", "slug": "e5f6g7h8-...", "url": "/venta/e5f6g7h8-..." }
        ]
      }
    ]
  }
]
```

---

### `POST /api/rrpp/`

Da de alta un nuevo RRPP. Crea el usuario con `rol=rrpp` y el perfil RRPP en una transacción atómica.

**Auth:** IsDueno

**Request:**
```json
{
  "nombre":          "Juan",
  "apellido":        "Pérez",
  "username":        "juanperez",
  "password":        "contraseña_temporal",
  "telefono":        "1123456789",
  "tipo_comision":   "fijo",
  "valor_comision":  500.00
}
```

**Response 201:**
```json
{
  "id":             1,
  "nombre":         "Juan Pérez",
  "username":       "juanperez",
  "tipo_comision":  "fijo",
  "valor_comision": 500.00,
  "asignaciones":   []
}
```

**Errores:**
- `400` — username ya existe, campos faltantes
- `403` — no es dueño

---

### `POST /api/rrpp/:id/asignar-evento/`

Asigna un RRPP a un evento. Genera automáticamente los 2 links (lista + venta_web).

**Auth:** IsDueno

**Request:**
```json
{
  "evento_id": 1
}
```

**Response 201:**
```json
{
  "asignacion_id": 5,
  "rrpp_nombre":   "Juan Pérez",
  "evento_nombre": "Noche Techno",
  "links": [
    { "tipo": "lista",     "slug": "a1b2c3d4-...", "url": "/lista/a1b2c3d4-..." },
    { "tipo": "venta_web", "slug": "e5f6g7h8-...", "url": "/venta/e5f6g7h8-..." }
  ]
}
```

**Errores:**
- `400` — evento no existe o no pertenece al boliche del dueño
- `409` — el RRPP ya está asignado a ese evento

---

### `GET /api/rrpp/mi-panel/`

Panel del RRPP autenticado. Ve sus asignaciones activas con métricas en vivo.

**Auth:** IsRRPP

**Response 200:**
```json
[
  {
    "evento_id":       1,
    "evento_nombre":   "Noche Techno",
    "evento_fecha":    "2026-08-05T23:00:00-03:00",
    "color_pulsera":   "violeta",
    "links": [
      { "tipo": "lista",     "slug": "a1b2c3d4-...", "url": "/lista/a1b2c3d4-..." },
      { "tipo": "venta_web", "slug": "e5f6g7h8-...", "url": "/venta/e5f6g7h8-..." }
    ],
    "estadisticas": {
      "anotados":   47,
      "ingresados": 31,
      "pendientes": 16,
      "rebotados":  2
    }
  }
]
```

---

### `POST /api/rrpp/anotar-invitado/`

Carga manual de un invitado a la lista. Equivalente a `POST /api/lista/:slug/anotar/` pero autenticado como RRPP.

**Auth:** IsRRPP

**Request:**
```json
{
  "slug_lista": "a1b2c3d4-...",
  "nombre":     "María",
  "apellido":   "López",
  "dni":        "38123456"
}
```

**Response 201:**
```json
{
  "id":     101,
  "nombre": "María López",
  "dni":    "38123456",
  "estado": "pendiente"
}
```

**Errores:**
- `400` — campos faltantes
- `403` — el link no pertenece al RRPP autenticado
- `409` — DNI ya anotado en ese evento

---

## 5. Lista pública

### `GET /api/lista/:slug/`

Información pública del link de lista. Usado por el cliente para ver a qué evento se está anotando.

**Auth:** Público

**Response 200:**
```json
{
  "evento": {
    "id":            1,
    "nombre":        "Noche Techno",
    "fecha":         "2026-08-05T23:00:00-03:00",
    "boliche":       "Club Crobar",
    "color_pulsera": "violeta"
  },
  "rrpp_nombre": "Juan Pérez",
  "link_activo": true,
  "anotados":    47
}
```

**Errores:**
- `404` — slug no existe
- `410` — link inactivo (evento cancelado)

---

### `POST /api/lista/:slug/anotar/`

El cliente se anota a la lista de un RRPP.

**Auth:** Público

**Request:**
```json
{
  "nombre":   "María",
  "apellido": "López",
  "dni":      "38123456"
}
```

**Response 201:**
```json
{
  "id":          101,
  "nombre":      "María López",
  "dni":         "38123456",
  "estado":      "pendiente",
  "evento":      "Noche Techno",
  "rrpp_nombre": "Juan Pérez",
  "mensaje":     "Te anotamos. Presentate en la puerta con tu DNI."
}
```

**Errores:**
- `400` — campos faltantes
- `404` — slug no existe
- `409` — DNI ya anotado en ese evento
- `410` — link inactivo

---

## 6. Puerta — Guardia

> Todos los endpoints de esta sección devuelven **423** si el evento está cancelado:
> ```json
> { "error": "SISTEMA BLOQUEADO - EVENTO CANCELADO", "motivo": "..." }
> ```

---

### `POST /api/puerta/guardia/escanear/`

Busca un asistente por QR o DNI. Primer paso del guardia.

**Auth:** IsGuardia

**Request (por QR):**
```json
{ "qr_code": "uuid-del-wallet-token" }
```

**Request (por DNI):**
```json
{ "dni": "38123456", "evento_id": 1 }
```

**Response 200:**
```json
{
  "id":           101,
  "nombre":       "María López",
  "dni":          "38123456",
  "tipo_ingreso": "lista_rrpp",
  "estado":       "pendiente",
  "rrpp_nombre":  "Juan Pérez"
}
```

**Errores:**
- `404` — no encontrado en la lista de ese evento
- `423` — evento cancelado

---

### `POST /api/puerta/guardia/aprobar/:id/`

Aprueba el ingreso. El asistente pasa a `aprobado_guardia` y puede ser atendido por cajera.

**Auth:** IsGuardia

**Request:** sin body

**Response 200:**
```json
{
  "id":          101,
  "estado":      "aprobado_guardia",
  "aprobado_at": "2026-08-06T01:23:45-03:00",
  "mensaje":     "Aprobado. Pasa a caja."
}
```

**Errores:**
- `400` — el asistente no está en estado `pendiente`
- `404` — asistente no existe
- `423` — evento cancelado

---

### `POST /api/puerta/guardia/rebotar/:id/`

Rechaza el acceso. Estado terminal — no puede ser revertido.

**Auth:** IsGuardia

**Request:**
```json
{
  "motivo": "Dress code"
}
```

**Response 200:**
```json
{
  "id":         101,
  "estado":     "rebotado_guardia",
  "rebotado_at":"2026-08-06T01:24:10-03:00",
  "motivo":     "Dress code"
}
```

**Errores:**
- `400` — el asistente no está en estado `pendiente`; o motivo vacío
- `404` — asistente no existe
- `423` — evento cancelado

---

## 7. Puerta — Cajera

> Todos los endpoints de esta sección devuelven **423** si el evento está cancelado.
> Todos devuelven **409** si el asistente no está en `aprobado_guardia`:
> ```json
> { "error": "Falta validación del guardia", "estado_actual": "pendiente" }
> ```

---

### `POST /api/puerta/cajera/escanear-web/:id/`

Segundo escaneo del QR para compras web. Ingreso automático sin cobro.

**Auth:** IsCajera

**Request:** sin body

**Response 200:**
```json
{
  "id":            101,
  "nombre":        "María López",
  "estado":        "ingresado_final",
  "metodo_pago":   "ya_pago_web",
  "ingresado_at":  "2026-08-06T01:25:00-03:00",
  "color_pulsera": "violeta",
  "mensaje":       "Ingreso confirmado. Entregar pulsera violeta."
}
```

**Errores:**
- `400` — el asistente no es de tipo `web_anticipada`
- `404` — asistente no existe
- `409` — no está en `aprobado_guardia`
- `423` — evento cancelado

---

### `POST /api/puerta/cajera/cobrar-lista/:id/`

Cobra a un asistente de lista RRPP en efectivo o transferencia.

**Auth:** IsCajera

**Request:**
```json
{
  "metodo_pago":  "efectivo",
  "monto_pagado": 5700
}
```

**Response 200:**
```json
{
  "id":            101,
  "nombre":        "María López",
  "estado":        "ingresado_final",
  "metodo_pago":   "efectivo",
  "monto_pagado":  5700,
  "ingresado_at":  "2026-08-06T01:25:30-03:00",
  "color_pulsera": "violeta",
  "mensaje":       "Ingreso confirmado. Entregar pulsera violeta."
}
```

**Errores:**
- `400` — método de pago inválido o monto faltante
- `404` — asistente no existe
- `409` — no está en `aprobado_guardia`
- `423` — evento cancelado

---

### `POST /api/puerta/cajera/venta-general/`

Venta en puerta sin lista previa. Crea N asistentes directamente en `ingresado_final`.

**Auth:** IsCajera

**Request:**
```json
{
  "evento_id": 1,
  "personas": [
    { "nombre": "Lucas", "apellido": "Torres", "dni": "40123456", "metodo_pago": "efectivo" },
    { "nombre": "Ana",   "apellido": "Gómez",  "dni": "41234567", "metodo_pago": "transferencia" }
  ]
}
```

**Response 201:**
```json
{
  "creados": 2,
  "color_pulsera": "violeta",
  "asistentes": [
    { "id": 102, "nombre": "Lucas Torres", "dni": "40123456", "estado": "ingresado_final" },
    { "id": 103, "nombre": "Ana Gómez",    "dni": "41234567", "estado": "ingresado_final" }
  ],
  "mensaje": "Ingreso confirmado. Entregar pulsera violeta."
}
```

**Errores:**
- `400` — datos faltantes o inválidos
- `409` — algún DNI ya está registrado en ese evento (incluye qué DNIs conflictúan)
- `423` — evento cancelado

---

### `POST /api/puerta/cajera/deshacer/:id/`

Revierte el ingreso de un asistente. Solo disponible dentro de los 10 minutos de `ingresado_at`.

**Auth:** IsCajera

**Request:** sin body

**Response 200:**
```json
{
  "id":     101,
  "estado": "aprobado_guardia",
  "mensaje":"Ingreso revertido. El asistente vuelve a estar pendiente de cobro."
}
```

**Errores:**
- `400` — el asistente no está en `ingresado_final`
- `403` — pasaron más de 10 minutos desde `ingresado_at`
- `404` — asistente no existe

---

## 8. Dashboard

### `GET /api/dashboard/aforo/:evento_id/`

Aforo en vivo. El frontend hace polling cada 3-5 segundos.

**Auth:** IsDueno, IsCajera, IsGuardia

**Response 200:**
```json
{
  "evento_id":  1,
  "ingresados": 342,
  "aforo_max":  800,
  "porcentaje": 42.75,
  "pendientes": 58
}
```

---

### `GET /api/dashboard/recaudacion/:evento_id/`

Desglose de recaudación del evento.

**Auth:** IsDueno

**Response 200:**
```json
{
  "evento_id": 1,
  "web": {
    "cantidad": 127,
    "monto_bruto":      723900,
    "comision_norware": 57912,
    "monto_neto":       665988
  },
  "efectivo": {
    "cantidad": 89,
    "monto":    507300
  },
  "transferencia": {
    "cantidad": 126,
    "monto":    718200
  },
  "total_recaudado":     1949400,
  "comision_norware_web": 57912
}
```

---

### `GET /api/dashboard/ranking-rrpp/:evento_id/`

Ranking de RRPP del evento con métricas de efectividad y comisiones a pagar.

**Auth:** IsDueno

**Response 200:**
```json
[
  {
    "rrpp_id":            1,
    "nombre":             "Juan Pérez",
    "tipo_comision":      "fijo",
    "valor_comision":     500.00,
    "anotados":           47,
    "ingresados":         31,
    "rebotados":          2,
    "tasa_conversion":    65.96,
    "recaudado_efectivo": 176700,
    "recaudado_transfer": 0,
    "recaudado_total":    176700,
    "comision_a_pagar":   15500
  }
]
```

> `comision_a_pagar` se calcula según `tipo_comision`:
> - `fijo`: `ingresados × valor_comision`
> - `porcentaje`: `recaudado_total × (valor_comision / 100)`

---

## 9. Pagos y Wallet

### `POST /api/pagos/preferencia/`

Crea una preferencia de pago en Mercado Pago y devuelve el link de checkout.

**Auth:** Público

**Request:**
```json
{
  "evento_id": 1,
  "nombre":    "María",
  "apellido":  "López",
  "dni":       "38123456",
  "email":     "maria@email.com",
  "cantidad":  1
}
```

**Response 200:**
```json
{
  "init_point":      "https://www.mercadopago.com.ar/checkout/v1/...",
  "preference_id":   "123456789-abcd-...",
  "precio_publicado": 5700,
  "desglose": {
    "precio_base":      5000,
    "fee_mp":           299.5,
    "fee_norware":      400.0,
    "precio_publicado": 5700
  }
}
```

**Errores:**
- `400` — datos faltantes o inválidos
- `404` — evento no existe
- `409` — DNI ya tiene entrada para ese evento
- `503` — error al crear preferencia en MP

---

### `POST /api/pagos/webhook/`

Recibe notificaciones de pago de Mercado Pago. Django valida la firma antes de procesar.

**Auth:** Público (validar header `x-signature` de MP)

**Request:** formato estándar de webhook de MP (notification de `payment`)

**Response 200:**
```json
{ "ok": true }
```

> Comportamiento al recibir pago aprobado:
> 1. Verifica que no exista `Asistente` con ese `mp_payment_id` (idempotencia)
> 2. Crea `Asistente` con `tipo_ingreso=web_anticipada`, `estado=aprobado_guardia`
> 3. Guarda `mp_payment_id` y `mp_fee_norware`
> 4. Envía mail al comprador con link `/wallet/:token`

**Errores:**
- `400` — firma MP inválida

---

### `GET /api/wallet/:token/`

Vista pública del ticket del comprador. Sin autenticación.

**Auth:** Público

**Response 200:**
```json
{
  "token":         "uuid-...",
  "nombre":        "María López",
  "dni":           "38123456",
  "estado":        "aprobado_guardia",
  "tipo_ingreso":  "web_anticipada",
  "evento": {
    "id":            1,
    "nombre":        "Noche Techno",
    "fecha":         "2026-08-05T23:00:00-03:00",
    "boliche":       "Club Crobar",
    "color_pulsera": "violeta"
  },
  "qr_code":       "uuid-wallet-token",
  "evento_cancelado": false,
  "motivo_cancelacion": null
}
```

> Si `evento_cancelado: true`, el frontend muestra el QR tachado y el mensaje de devolución.

**Errores:**
- `404` — token no existe

---

## 10. Admin Norware

### `GET /api/admin/metricas/`

Métricas globales de la plataforma. Solo para el rol `superadmin`.

**Auth:** IsSuperAdmin

**Response 200:**
```json
{
  "totales": {
    "entradas_web_total":          1250,
    "comision_norware_total":      575000,
    "eventos_activos":             3,
    "eventos_cancelados":          1
  },
  "por_evento": [
    {
      "evento_id":              1,
      "evento_nombre":          "Noche Techno",
      "boliche":                "Club Crobar",
      "fecha":                  "2026-08-05T23:00:00-03:00",
      "estado":                 "activo",
      "entradas_web":           127,
      "comision_norware":       57912,
      "recaudado_total_web":    723900,
      "fee_mp_estimado":        43341
    }
  ]
}
```

---

## Códigos de error comunes

| Código | Significado en esta API |
|--------|------------------------|
| `400` | Request malformado o datos inválidos |
| `401` | Token ausente, inválido o expirado |
| `403` | Token válido pero el rol no tiene acceso |
| `404` | Recurso no encontrado |
| `405` | Método no permitido (ej: DELETE en evento con asistentes) |
| `409` | Conflicto de estado (ej: DNI duplicado, estado incorrecto) |
| `410` | Recurso inactivo (ej: link de RRPP inactivo) |
| `423` | Recurso bloqueado (evento cancelado) |
| `503` | Error de servicio externo (Mercado Pago) |

---

## Notas de implementación

- Todos los timestamps son ISO 8601 con timezone `-03:00` (Argentina, UTC-3)
- Los montos son en pesos argentinos (ARS), sin centavos en la respuesta (entero)
- Los porcentajes de tasas de conversión son floats con 2 decimales
- El campo `color_pulsera` es un string libre que el dueño carga al crear el evento (ej: `"violeta"`, `"roja"`, `"#FF0000"`)
- Los slugs de LinkRRPP son UUIDs v4 — no guessables
- El `wallet_token` de Asistente es UUID v4 — no guessable, no se expone el ID numérico en URLs públicas
