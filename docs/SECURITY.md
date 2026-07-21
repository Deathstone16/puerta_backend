# Norware Backend — Análisis de Seguridad y Hardening

Fecha: 21 de julio de 2026

---

## Resumen ejecutivo

El backend tiene una base sólida (JWT, permisos por rol, ORM sin SQL crudo) pero falta hardening para producción. Las áreas críticas a resolver antes del evento del 5/8:

| Prioridad | Issue | Riesgo |
|-----------|-------|--------|
| ALTA | Sin rate limiting | Brute force en login, DDoS en webhook MP |
| ALTA | Webhook MP sin validación de firma | Inyección de asistentes falsos |
| ALTA | SECRET_KEY en código (fallback inseguro) | Forja de JWT |
| MEDIA | CORS sin restricción de métodos/headers | Requests no deseados |
| MEDIA | Sin headers de seguridad HTTP | XSS, clickjacking, MIME sniffing |
| MEDIA | JWT access token de 8h sin rotación | Window de ataque largo si se roba un token |
| MEDIA | Sin logging de auditoría | No hay rastro de operaciones críticas |
| BAJA | Swagger UI expuesto en producción | Información interna accesible |
| BAJA | DEBUG=True como default | Stack traces expuestos |

---

## 1. Rate Limiting (CRÍTICO)

**Problema:** No hay rate limiting en ningún endpoint. Un atacante puede:
- Brute force el login (probando miles de contraseñas por segundo)
- Spamear el webhook de MP para saturar la DB
- DDoS los endpoints públicos de lista/anotación
- Flood la creación de preferencias MP

**Solución:** `django-ratelimit` o `djangorestframework-throttling` (ya incluido en DRF).

**Configuración recomendada:**
```
Login:          5 intentos / minuto por IP
Refresh:        10 / minuto por IP
Preferencia MP: 3 / minuto por IP (anti-fraude)
Webhook:        60 / minuto por IP (MP envía ráfagas)
Anotar lista:   10 / minuto por IP
Guardia/Cajera: 120 / minuto por usuario (operación rápida en noche)
Público (GET):  60 / minuto por IP
```

---

## 2. Webhook MP sin validación de firma (CRÍTICO)

**Problema:** `POST /api/pagos/webhook/` acepta cualquier request sin validar que provenga de MP.
Un atacante puede enviar un POST manual con un payment_id inventado y crear asistentes falsos con `estado=aprobado_guardia`.

**Solución:** Validar la firma HMAC que MP envía en el header `x-signature`.

```python
import hmac, hashlib
from django.conf import settings

def _validar_firma_mp(request):
    x_signature = request.headers.get('x-signature', '')
    x_request_id = request.headers.get('x-request-id', '')
    # Extraer ts y v1 del x-signature
    parts = dict(p.split('=', 1) for p in x_signature.split(',') if '=' in p)
    ts = parts.get('ts', '')
    v1 = parts.get('v1', '')
    
    # Construir el manifest
    data_id = request.query_params.get('data.id', '')
    manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
    
    # Calcular HMAC
    expected = hmac.new(
        settings.MP_WEBHOOK_SECRET.encode(),
        manifest.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(v1, expected)
```

---

## 3. CORS — Configuración actual vs recomendada

**Actual:**
```python
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='http://localhost:5173').split(',')
```

**Falta:**
- `CORS_ALLOW_CREDENTIALS = True` (para que el frontend pueda enviar cookies si es necesario)
- `CORS_ALLOW_METHODS` restringido
- `CORS_ALLOW_HEADERS` explícito
- En producción, solo el dominio del frontend

**Recomendado:**
```python
CORS_ALLOWED_ORIGINS = [...]  # Solo dominios de producción + localhost en dev
CORS_ALLOW_METHODS = ['GET', 'POST', 'PATCH', 'OPTIONS']  # Sin PUT, DELETE no necesario
CORS_ALLOW_HEADERS = ['authorization', 'content-type', 'x-requested-with']
CORS_ALLOW_CREDENTIALS = False  # JWT va en header, no en cookie
CORS_PREFLIGHT_MAX_AGE = 86400  # Cache preflight 24h
```

---

## 4. JWT — Análisis

**Token lifetime actual:** 8h access, 7d refresh.

**Riesgo:** Si un token es robado, el atacante tiene 8 horas para operar.

**Mitigaciones:**
- Access token de 2h (suficiente para una noche de evento) en vez de 8h
- `ROTATE_REFRESH_TOKENS = True` + `BLACKLIST_AFTER_ROTATION = True` — cada refresh invalida el anterior
- El claim `rol` en el JWT permite al frontend redirigir sin request adicional — esto está correcto
- No guardar tokens en `localStorage` — recomendar al frontend usar memory o httpOnly cookie

**Token blacklisting:** Agregar `rest_framework_simplejwt.token_blacklist` a INSTALLED_APPS para poder invalidar tokens robados vía admin.

---

## 5. Headers de seguridad HTTP

**Falta configurar en producción:**
```python
# En settings.py
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000  # 1 año
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True  # Solo en producción
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

---

## 6. Validación de inputs

**Estado actual:** DRF serializers hacen validación básica de tipos. Pero falta:

- **DNI:** no se valida formato (solo `.strip()`). Debería ser numérico, 7-8 dígitos.
- **Email:** no se valida formato en `PreferenciaView`
- **Nombre/Apellido:** sin límite de caracteres en los views (solo el model tiene max_length)
- **precio_base:** bien validado en `calcular_precio_publicado` (ValueError si <= 0)
- **line_up JSON:** no se valida estructura — un atacante puede inyectar JSON arbitrario enorme

**Recomendaciones:**
- Validar DNI: regex `^\d{7,8}$`
- Validar email con `EmailField` de DRF
- Limitar tamaño de body en settings: `DATA_UPLOAD_MAX_MEMORY_SIZE`
- Validar estructura de `line_up` con un serializer anidado

---

## 7. Protección del Admin de Django

**Riesgo:** El admin de Django está en `/admin/` con la URL por defecto. Es target de bots.

**Recomendaciones:**
- Cambiar URL a algo no predecible: `path('norware-admin-{hash}/', admin.site.urls)`
- O mejor: proteger con 2FA (django-otp)
- En producción: restringir acceso por IP o VPN

---

## 8. Logging y auditoría

**Falta:** No hay logging de operaciones críticas de negocio.

**Operaciones que deberían loguearse:**
- Login exitoso/fallido (IP, username)
- Cambio de estado de asistente (quién, cuándo, de qué a qué)
- Cancelación de evento
- Conexión OAuth de MP
- Reembolsos procesados/fallidos
- Errores de webhook

**Implementación:** Crear un middleware de auditoría o usar signals para loguear transiciones de estado.

---

## 9. Swagger UI en producción

**Riesgo:** `/api/schema/swagger-ui/` expone la estructura completa de la API incluyendo endpoints internos.

**Solución:** Condicionarlo a `DEBUG`:
```python
if DEBUG:
    urlpatterns += [
        path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
        path('api/schema/swagger-ui/', ...),
    ]
```

---

## 10. Protección de datos sensibles

**Campos sensibles en Boliche:**
- `mp_access_token` y `mp_refresh_token` son credentials — NUNCA deben exponerse en la API

**Estado actual:** El `BolicheSerializer` no incluye estos campos (solo `mp_connected` boolean) ✅

**Recomendación adicional:** Encriptar los tokens en la DB con `django-encrypted-model-fields` o similar para proteger ante dump de DB.

---

## 11. Protección contra enumeración

**Riesgo:** Endpoints públicos permiten enumerar datos:
- `GET /api/eventos/` → lista todos los eventos (intencional, es la cartelera)
- `GET /api/lista/:slug/` → UUID no guessable ✅
- `GET /api/wallet/:token/` → UUID no guessable ✅

**OK:** Los slugs y tokens son UUID4 — imposibles de enumerar.

---

## Implementación aplicada

Se implementan los siguientes cambios:
1. Rate limiting con DRF throttling
2. Validación de firma del webhook MP (header `x-signature`)
3. CORS hardened
4. Headers de seguridad para producción
5. JWT con blacklist y rotación
6. Validación de DNI y email
7. Swagger solo en DEBUG
8. DATA_UPLOAD_MAX_MEMORY_SIZE limitado
