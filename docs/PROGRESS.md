# Norware Backend — Progreso de implementación

Última actualización: 21 de julio de 2026

---

## Estado de las apps

| App | Estado | Tests | Endpoints disponibles |
|-----|--------|-------|----------------------|
| `cuentas` | ✅ Completa | 24/24 | `POST /api/auth/login/`, `POST /api/auth/refresh/` |
| `boliches` | ✅ Completa | 17/17 | `POST /api/boliches/`, `GET /api/boliches/mio/`, `PATCH /api/boliches/:id/` |
| `eventos` | ✅ Completa | 37/37 | `GET /api/eventos/`, `GET /api/eventos/:id/`, `POST /api/eventos/crear/`, `PATCH /api/eventos/:id/`, `POST /api/eventos/:id/cancelar/`, `GET /api/precios/calcular/` |
| `rrpp` | ✅ Completa | 19/19 | `GET /api/rrpp/`, `POST /api/rrpp/`, `POST /api/rrpp/:id/asignar-evento/`, `GET /api/rrpp/mi-panel/`, `POST /api/rrpp/anotar-invitado/` |
| `puerta` | ✅ Completa | 31/31 | `GET /api/lista/:slug/`, `POST /api/lista/:slug/anotar/`, `POST /api/puerta/guardia/escanear/`, `POST /api/puerta/guardia/aprobar/:id/`, `POST /api/puerta/guardia/rebotar/:id/`, `POST /api/puerta/cajera/escanear-web/:id/`, `POST /api/puerta/cajera/cobrar-lista/:id/`, `POST /api/puerta/cajera/venta-general/`, `POST /api/puerta/cajera/deshacer/:id/`, `GET /api/dashboard/aforo/:evento_id/` |
| `pagos` | ✅ Completa | 21/21 | `POST /api/pagos/preferencia/`, `POST /api/pagos/webhook/`, `GET /api/wallet/:token/`, `GET /api/dashboard/recaudacion/:evento_id/`, `GET /api/dashboard/ranking-rrpp/:evento_id/`, `GET /api/admin/metricas/` |

**Total tests pasando: 149**

---

## Endpoints listos para consumir desde el frontend

### Auth

```
POST /api/auth/login/
  Body: { "username": "...", "password": "..." }
  Response 200: { "access": "jwt...", "refresh": "jwt...", "rol": "dueno", "nombre": "Carlos García", "id": 2 }

POST /api/auth/refresh/
  Body: { "refresh": "jwt..." }
  Response 200: { "access": "jwt..." }
```

### Boliches (requiere JWT con rol=dueno)

```
POST /api/boliches/
  Body: { "nombre": "...", "direccion": "...", "collector_id_mp": "..." }
  Response 201: { "id", "nombre", "direccion", "collector_id_mp", "created_at" }

GET /api/boliches/mio/
  Response 200: { "id", "nombre", "direccion", "collector_id_mp", "created_at" }

PATCH /api/boliches/:id/
  Body: cualquier subconjunto de { "nombre", "direccion", "collector_id_mp" }
  Response 200: boliche actualizado
```

### Eventos

```
GET /api/eventos/                          (público)
  Query: ?estado=activo|cancelado (opcional)
  Response 200: [ { "id", "nombre", "fecha", "color_pulsera", "precio_base", "precio_publicado", "aforo_max", "estado", "boliche": { "id", "nombre", "direccion" } } ]

GET /api/eventos/:id/                      (público)
  Response 200: { ...campos de lista + "line_up", "desglose_precio": { "precio_base", "fee_mp", "fee_norware", "precio_publicado" }, "motivo_cancelacion", "created_at", "updated_at" }

POST /api/eventos/crear/                   (IsDueno)
  Body: { "boliche_id", "nombre", "fecha", "aforo_max", "color_pulsera", "precio_base", "line_up" }
  Response 201: detalle completo del evento

PATCH /api/eventos/:id/                    (IsDueno, solo su boliche)
  Body: cualquier subconjunto de campos editables
  Response 200 | 405 si cancelado

POST /api/eventos/:id/cancelar/            (IsDueno)
  Body: { "motivo": "..." }
  Response 200: { "id", "estado", "motivo_cancelacion", "reembolsos_iniciados" }

GET /api/precios/calcular/?precio_base=X   (público)
  Response 200: { "precio_base", "fee_mp", "fee_norware", "precio_publicado" }
```

### RRPP

```
GET /api/rrpp/                             (IsDueno)
  Response 200: [ { "id", "nombre", "username", "tipo_comision", "valor_comision", "asignaciones": [...] } ]

POST /api/rrpp/                            (IsDueno)
  Body: { "nombre", "apellido", "username", "password", "telefono", "tipo_comision", "valor_comision" }
  Response 201

POST /api/rrpp/:id/asignar-evento/         (IsDueno)
  Body: { "evento_id": N }
  Response 201: { "asignacion_id", "rrpp_nombre", "evento_nombre", "links": [{ "tipo", "slug", "activo", "url" }] }

GET /api/rrpp/mi-panel/                    (IsRRPP)
  Response 200: [ { "evento_id", "evento_nombre", "evento_fecha", "color_pulsera", "activa", "links": [...], "estadisticas": { "anotados", "ingresados", "pendientes", "rebotados" } } ]

POST /api/rrpp/anotar-invitado/            (IsRRPP)
  Body: { "slug_lista": "uuid", "nombre", "apellido", "dni" }
  Response 201: { "id", "nombre", "dni", "estado" }
```

### Puerta (en desarrollo)

```
GET  /api/lista/:slug/                     (público)
POST /api/lista/:slug/anotar/              (público)
POST /api/puerta/guardia/escanear/         (IsGuardia)
POST /api/puerta/guardia/aprobar/:id/      (IsGuardia)
POST /api/puerta/guardia/rebotar/:id/      (IsGuardia)
POST /api/puerta/cajera/escanear-web/:id/  (IsCajera)
POST /api/puerta/cajera/cobrar-lista/:id/  (IsCajera)
POST /api/puerta/cajera/venta-general/     (IsCajera)
POST /api/puerta/cajera/deshacer/:id/      (IsCajera)
GET  /api/dashboard/aforo/:evento_id/      (IsGuardia|IsCajera|IsDueno)
```

### Pagos (pendiente)

```
POST /api/pagos/preferencia/               (público)
POST /api/pagos/webhook/                   (público, MP)
GET  /api/wallet/:token/                   (público)
GET  /api/dashboard/recaudacion/:evento_id/ (IsDueno)
GET  /api/admin/metricas/                  (IsSuperAdmin)
```

---

## Usuarios de prueba (fixture)

| username | password | rol |
|----------|----------|-----|
| `admin` | `admin123` | superadmin |
| `carlos_dueno` | `dueno123` | dueno |
| `juan_rrpp` | `rrpp123` | rrpp |
| `maria_guardia` | `guardia123` | guardia |
| `ana_cajera` | `cajera123` | cajera |

Cargar con: `python manage.py loaddata usuarios_prueba`

---

## Cómo consumir la API desde el frontend

1. **Login:** `POST /api/auth/login/` → guardar `access` y `refresh`
2. **Headers:** `Authorization: Bearer {access}` en cada request autenticado
3. **Refresh:** antes de que expire (8h), `POST /api/auth/refresh/` con el refresh token
4. **Redirigir por rol:** leer `rol` del body del login y redirigir:
   - `dueno` → `/dashboard`
   - `rrpp` → `/rrpp`
   - `guardia` → `/guardia`
   - `cajera` → `/cajera`
   - `superadmin` → `/admin`

---

## Para levantar el backend

```bash
cd puerta_backend
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
cd api
python manage.py migrate
python manage.py loaddata usuarios_prueba
python manage.py runserver
```

API disponible en `http://localhost:8000/api/`
Swagger UI en `http://localhost:8000/api/schema/swagger-ui/`
