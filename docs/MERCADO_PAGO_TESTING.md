# Fix: Mercado Pago — pago en modo prueba (sandbox)

Fecha: 2026-08-02
Estado: implementado y verificado con tests (pendiente de deploy + retest en Render)

---

## 1. Resumen del problema

Al intentar pagar una entrada desde el checkout de Mercado Pago, el comprador veía la
pantalla de error genérica **"Oh no, algo anduvo mal"** y el pago nunca se procesaba.

El error ocurría **siempre**, sin importar:
- si se cobraba con `marketplace_fee` o sin él (se probó comentando la línea en `mp_client.py`),
- cuánto saldo tuviera cargado el comprador ($50.000 cargados, sin efecto),
- si el pago se intentaba con saldo en cuenta.

## 2. Diagnóstico (cómo se encontró la causa raíz)

### 2.1 Pistas obtenidas de la URL de error

Cuando el checkout falla, Mercado Pago redirige a una URL de error que contiene un JWT.
Decodificando ese JWT (base64) se obtuvo:

```json
{
  "sub": "3577381646",
  "protected_data": { "amount": 2508, "currency_id": "ARS" },
  "sandbox": "false"
}
```

- `sub: 3577381646` = el **comprador de prueba** (`TESTUSER6400151229337286662`). El pago
  se intentó con la cuenta correcta.
- `sandbox: "false"` = **la preferencia se creó en producción**, no en el entorno de prueba.
  Ese es el problema: un comprador de prueba (sandbox) no puede pagar una preferencia de producción.

### 2.2 Verificación en la base de datos (Supabase Table Editor)

Tabla `boliches_boliche` — los 3 tokens OAuth guardados eran **todos de producción**:

| Boliche | mp_user_id | Prefijo del token |
|---|---|---|
| valentin fluss | 3559181075 (test user viejo) | `APP_USR-...` |
| Bruno Camors | 3577381648 (test seller) | `APP_USR-...` |
| juanse sirich | 3577381648 (test seller) | `APP_USR-...` |

Los 3 OAuth se hicieron logueándose con **usuarios de prueba**, pero Mercado Pago devolvió
tokens `APP_USR-` (producción) en vez de `TEST-` (sandbox). Es determinístico, no fue un
error de cuenta.

### 2.3 Confirmación experimental (curl)

La documentación oficial de MP documenta el parámetro `test_token: true` en el endpoint
`POST /oauth/token` para generar credenciales de sandbox. Probando con el `refresh_token`
ya guardado (sin tocar código):

```
curl.exe -X POST "https://api.mercadopago.com/oauth/token" -H "Content-Type: application/json" -d '{"grant_type":"refresh_token","client_id":"4461326892813637","client_secret":"<SECRET>","refresh_token":"TG-6a6f8a90224bf5000174f9e1-3577381648","test_token":"true"}'
```

Resultado:

```json
{
  "access_token": "TEST-4461326892813637-080215-03c06132385a6399f627e470aef27072-3577381648",
  "user_id": 3577381648
}
```

**Confirmado:** con `test_token: true`, MP emite token `TEST-` (sandbox) para el vendedor de
prueba. El código del backend no enviaba ese parámetro — esa era la causa raíz.

## 3. Causa raíz

> El intercambio OAuth (`POST /oauth/token`) del backend **no enviaba `test_token: true`**,
> por lo que Mercado Pago devolvía tokens `APP_USR-` (producción) aunque el dueño conectara
> su cuenta de prueba. Las preferencias de pago se creaban en producción, y el comprador de
> prueba no puede pagarlas → error genérico en el checkout.

## 4. Cambios realizados

### 4.1 `api/config/settings.py` — nueva variable de entorno

Agregada junto a la config de MP (línea ~221):

```python
MP_TEST_MODE = config('MP_TEST_MODE', default=False, cast=bool)
```

- `False` por defecto → **sin cambios de comportamiento** en producción o en local sin configurar.
- Se activa con la variable de entorno `MP_TEST_MODE=true`.

### 4.2 `api/apps/boliches/views.py` — `test_token` en OAuth

**`_exchange_code_for_token()`** (canje del `code` de autorización): se agregó el parámetro
al payload, solo si `MP_TEST_MODE` está activo:

```python
payload = {
    'client_id': settings.MP_APP_ID,
    'client_secret': settings.MP_CLIENT_SECRET,
    'code': code,
    'grant_type': 'authorization_code',
    'redirect_uri': settings.MP_REDIRECT_URI,
}
if settings.MP_TEST_MODE:
    payload['test_token'] = True
```

**`refresh_mp_token()`** (renovación del token): mismo parámetro, también condicionado a
`MP_TEST_MODE`. Esto es **crítico**: el refresh regenera el token y, si no enviara
`test_token`, lo pisaría volviendo a `APP_USR-` (los tokens duran ~180 días y se renuevan
solo).

**Logging nuevo** para verificar sin necesidad de la base de datos:
- Al conectar: `Boliche {id} conectado a MP (user_id={id}, token={prefijo})`
- Al renovar: `Token MP renovado para boliche {id} (token={prefijo})`

El prefijo (`TEST-` / `APP_USR-`) permite confirmar el entorno en los logs de Render.

### 4.3 `api/apps/boliches/tests.py` — test actualizado

`test_connect_sin_boliche_devuelve_400` fue renombrado a
`test_connect_sin_boliche_devuelve_auth_url`: el dueño **no necesita tener boliche** para
conectar MP — el boliche se crea solo en el callback. El test viejo reflejaba un
comportamiento que ya no existe.

### 4.4 `api/apps/eventos/tests.py` — test actualizado

`test_crear_evento_boliche_ajeno_devuelve_403` fue reemplazado por
`test_crear_evento_con_boliche_ajeno_usa_boliche_propio`: al crear un evento, el `boliche_id`
del payload se ignora y se asigna el boliche del propio organizador (o `None` si no tiene).
El dueño puede crear un evento **antes** de conectar MP y empezar a cobrar después.

### 4.5 Sin cambios (por ahora)

- `api/apps/pagos/mp_client.py`: tiene el `marketplace_fee` comentado (cambio local tuyo,
  sin commitear). No se tocó: sirve para probar sin split de pagos.
- Migraciones: no hace falta ninguna.

## 5. Verificación con tests

Suite completa local (Python 3.12, SQLite, con `DEBUG=True`):

```
SECRET_KEY=... DEBUG=True python manage.py test
```

Resultado: **168/171 pasan**. Los 3 fallos restantes son **pre-existentes** y ajenos a este
fix (app `rrpp`, bug ya documentado del flujo de invitados):

| Test | Bug relacionado |
|---|---|
| `test_alta_rrpp_exitosa_crea_usuario_y_perfil` | Flujo RRPP |
| `test_aprobar_invitado_persiste_estado` | `AprobarInvitadoView` no cambia `estado` (queda `pendiente`) |
| `test_mi_panel_incluye_link_personal_y_slug` | Flujo RRPP |

## 6. Deploy y retest (checklist para Render)

1. **Push a `main`** (Render deployea desde `main`) con estos 3 archivos:
   - `api/config/settings.py`
   - `api/apps/boliches/views.py`
   - `api/apps/boliches/tests.py`, `api/apps/eventos/tests.py` (tests)
2. **Render → puerta-backend → Environment** → agregar variable: `MP_TEST_MODE=true`
3. **Redeploy** (el build corre las migraciones solo, no hace falta ninguna nueva)
4. En el frontend, **reconectar Mercado Pago** logueándose en la pantalla de autorización
   con el vendedor de prueba:
   - Usuario: `TESTUSER5928770266605208120`
   - Contraseña: `czaAEJIKYR`
   - Código de 6 dígitos: `381648` (últimos 6 dígitos del User ID, tal como pide MP)
5. **Verificar en logs de Render** que aparece:
   `Boliche X conectado a MP (user_id=3577381648, token=TEST-)`
   (o en Supabase Table Editor → `boliches_boliche` → el token ahora empieza `TEST-`)
6. **Retest del pago** — requisitos según doc oficial de MP:
   - Usar una **pestaña de incógnito** (evita conflictos de sesión entre vendedor/comprador)
   - Loguearse en el checkout como comprador de prueba: `TESTUSER6400151229337286662` /
     `fG6tXW7yHU` / código `381646`
   - Probar con **saldo en cuenta** ($50.000 cargados) y con **tarjeta APRO**:
     `5031 7557 3453 0604` / CVV `123` / fecha de vencimiento futura / titular `APRO`
7. **Verificar el webhook**: con `TEST-` deberían llegar las notificaciones de pago al backend.

## 7. Volver a producción (cuando corresponda)

1. En Render: `MP_TEST_MODE=false` (o eliminar la variable)
2. Los dueños conectan sus **cuentas reales** de Mercado Pago → MP devuelve `APP_USR-` (correcto en producción)
3. Restaurar el `marketplace_fee` en `mp_client.py` cuando el split de pagos esté activo
   (actualmente comentado para la prueba)

Con el flag apagado el código queda **idéntico al comportamiento original**: nada de lo
existente cambia.

## 8. Pendientes / observaciones

1. **App "Debajo de lo ideal" en MP**: no se pudo determinar qué paso de la checklist falta.
   Puede influir en el OAuth de test users y en salir a producción. Revisar en el panel de
   desarrolladores (app `puerta`, ID `4461326892813637`).
2. **Admin de Django da 500 en la tabla Boliches**: sin resolver (no bloquea, se usa
   Supabase Table Editor). Diagnóstico pendiente: buscar el `Traceback` en logs de Render.
3. **Bugs RRPP** (3 tests fallando): documentados, fuera del alcance de este fix.
4. **Seguridad**: el `MP_CLIENT_SECRET` quedó expuesto en un chat. Considerar rotarlo en el
   panel de MP (Tus integraciones → Credenciales → Renovar).
5. **Tokens de prueba**: si el token `TEST-` expira (~180 días), el `refresh_mp_token` lo
   renueva con `test_token: true` gracias al fix — no requiere reconectar OAuth.

## 9. Datos de referencia de las cuentas de prueba

| Rol | Usuario | ID | Contraseña | Código |
|---|---|---|---|---|
| Vendedor | `TESTUSER5928770266605208120` | 3577381648 | `czaAEJIKYR` | `381648` |
| Comprador | `TESTUSER6400151229337286662` | 3577381646 | `fG6tXW7yHU` | `381646` |
| Marketplace | `TESTUSER7902...` | 3573592944 | — | — |

Tarjeta de prueba APRO: `5031 7557 3453 0604` — CVV `123` — vencimiento futuro — titular `APRO`.
