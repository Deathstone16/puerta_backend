# Documento de Requisitos — `cuentas`: Auth, Usuarios y Roles

## Introducción

La app `cuentas` es el núcleo de autenticación y autorización de Norware. Gestiona el modelo de usuario personalizado con soporte de roles, los permisos custom basados en rol y los endpoints de autenticación JWT.

Norware es una plataforma de venta de entradas y control de acceso para boliches en Argentina. El sistema de roles define qué puede hacer cada persona en la plataforma: desde el superadmin que supervisa toda la plataforma hasta el guardia que controla el acceso en la puerta.

El modelo de usuario extiende `AbstractUser` de Django y agrega los campos `rol` y `telefono`. La autenticación es stateless con SimpleJWT, y el token incluye el campo `rol` como claim personalizado para que el frontend pueda redirigir al usuario al panel correcto sin un request adicional.

## Glosario

- **Sistema**: La aplicación backend de Norware (Django + DRF).
- **Usuario**: Instancia del modelo `cuentas.Usuario`, que extiende `AbstractUser`.
- **Autenticador**: Componente que valida credenciales y emite tokens JWT (`LoginView`).
- **TokenRefresher**: Componente que renueva el access token a partir de un refresh token válido.
- **PermisoRol**: Clase de permiso DRF que verifica que el usuario autenticado tenga el rol correspondiente (`IsSuperAdmin`, `IsDueno`, `IsRRPP`, `IsGuardia`, `IsCajera`).
- **AccessToken**: JWT de corta duración (8 horas) que autoriza requests a endpoints protegidos.
- **RefreshToken**: JWT de larga duración (7 días) que permite obtener nuevos access tokens sin re-autenticarse.
- **Rol**: Atributo del usuario que define su función en la plataforma. Valores posibles: `superadmin`, `dueno`, `rrpp`, `guardia`, `cajera`.
- **Claim personalizado**: Campo extra incluido en el payload del JWT más allá de los claims estándar.
- **Fixtures**: Archivo JSON cargable con `manage.py loaddata` que contiene datos de prueba predefinidos.

---

## Requisitos

### Requisito 1: Modelo de usuario con rol y teléfono

**Historia de usuario:** Como desarrollador del sistema, quiero que el modelo `Usuario` incluya un campo `rol` obligatorio con valores controlados y un campo `telefono` opcional, para que el sistema pueda diferenciar qué puede hacer cada usuario en la plataforma.

#### Criterios de aceptación

1. THE Sistema SHALL definir el modelo `Usuario` como extensión de `AbstractUser` de Django con los campos `rol` y `telefono`.
2. THE Sistema SHALL validar que el campo `rol` solo acepte los valores `superadmin`, `dueno`, `rrpp`, `guardia` o `cajera`.
3. THE Sistema SHALL requerir que el campo `rol` no sea nulo ni vacío en ningún usuario.
4. THE Sistema SHALL aceptar el campo `telefono` como opcional (puede ser nulo o vacío).
5. THE Sistema SHALL registrar `AUTH_USER_MODEL = 'cuentas.Usuario'` en la configuración de Django.
6. WHEN se crea una migración de base de datos, THE Sistema SHALL incluir el campo `rol` como `CharField` con `choices`, `max_length=20`, sin valor por defecto (para forzar asignación explícita al crear usuarios).

### Requisito 2: Permisos custom basados en rol

**Historia de usuario:** Como desarrollador del sistema, quiero que existan clases de permiso DRF por cada rol, para que las vistas puedan proteger sus endpoints de manera declarativa según el rol requerido.

#### Criterios de aceptación

1. THE Sistema SHALL implementar las clases `IsSuperAdmin`, `IsDueno`, `IsRRPP`, `IsGuardia` e `IsCajera` en `apps/cuentas/permissions.py`.
2. WHEN un request llega a una vista protegida con `IsDueno`, THE PermisoRol SHALL conceder acceso solo si el usuario está autenticado y su `rol` es exactamente `dueno`.
3. WHEN un request llega a una vista protegida con `IsRRPP`, THE PermisoRol SHALL conceder acceso solo si el usuario está autenticado y su `rol` es exactamente `rrpp`.
4. WHEN un request llega a una vista protegida con `IsGuardia`, THE PermisoRol SHALL conceder acceso solo si el usuario está autenticado y su `rol` es exactamente `guardia`.
5. WHEN un request llega a una vista protegida con `IsCajera`, THE PermisoRol SHALL conceder acceso solo si el usuario está autenticado y su `rol` es exactamente `cajera`.
6. WHEN un request llega a una vista protegida con `IsSuperAdmin`, THE PermisoRol SHALL conceder acceso solo si el usuario está autenticado y su `rol` es exactamente `superadmin`.
7. IF el usuario no está autenticado, THEN THE PermisoRol SHALL denegar acceso devolviendo HTTP 403.
8. IF el usuario está autenticado pero su rol no coincide con el requerido por la vista, THEN THE PermisoRol SHALL denegar acceso devolviendo HTTP 403.

### Requisito 3: Endpoint de login con claim de rol en JWT

**Historia de usuario:** Como usuario del sistema (cualquier rol), quiero poder autenticarme enviando mi `username` y `password`, para obtener un JWT que incluya mi rol y así el frontend me redirija al panel correcto sin un request adicional.

#### Criterios de aceptación

1. THE Sistema SHALL exponer el endpoint `POST /api/auth/login/` sin requerir autenticación previa.
2. WHEN un cliente envía `username` y `password` válidos a `POST /api/auth/login/`, THE Autenticador SHALL devolver HTTP 200 con un cuerpo JSON que contenga los campos `access`, `refresh`, `rol`, `nombre` e `id`.
3. THE Autenticador SHALL incluir el valor del campo `rol` del usuario en el campo `rol` de la respuesta JSON.
4. THE Autenticador SHALL construir el campo `nombre` de la respuesta concatenando `first_name` y `last_name` del usuario.
5. THE Autenticador SHALL incluir el `id` numérico del usuario en la respuesta.
6. THE Autenticador SHALL emitir un `access` token con duración de 8 horas.
7. THE Autenticador SHALL emitir un `refresh` token con duración de 7 días.
8. THE Autenticador SHALL incluir el campo `rol` como claim personalizado dentro del payload del JWT `access`, de modo que el frontend pueda decodificar el token y conocer el rol sin hacer un request adicional.
9. IF el cliente envía credenciales incorrectas, THEN THE Autenticador SHALL devolver HTTP 401.
10. IF el cliente envía un cuerpo JSON sin los campos `username` o `password`, THEN THE Autenticador SHALL devolver HTTP 400.

### Requisito 4: Endpoint de renovación de access token

**Historia de usuario:** Como usuario del sistema, quiero poder renovar mi access token usando el refresh token, para mantener mi sesión activa sin necesidad de volver a ingresar mis credenciales.

#### Criterios de aceptación

1. THE Sistema SHALL exponer el endpoint `POST /api/auth/refresh/` sin requerir autenticación previa.
2. WHEN un cliente envía un `refresh` token válido y vigente a `POST /api/auth/refresh/`, THE TokenRefresher SHALL devolver HTTP 200 con un nuevo `access` token en el cuerpo JSON.
3. IF el cliente envía un `refresh` token expirado, THEN THE TokenRefresher SHALL devolver HTTP 401.
4. IF el cliente envía un `refresh` token con firma inválida o formato incorrecto, THEN THE TokenRefresher SHALL devolver HTTP 401.
5. IF el cliente envía un cuerpo JSON sin el campo `refresh`, THEN THE TokenRefresher SHALL devolver HTTP 400.

### Requisito 5: Configuración de DRF, SimpleJWT, CORS y drf-spectacular

**Historia de usuario:** Como desarrollador del sistema, quiero que `config/settings.py` incluya la configuración completa de DRF, SimpleJWT, CORS y drf-spectacular, para que todos los endpoints estén protegidos por JWT por defecto y el esquema OpenAPI sea generado automáticamente.

#### Criterios de aceptación

1. THE Sistema SHALL configurar `REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES']` con `JWTAuthentication` de SimpleJWT como único método de autenticación.
2. THE Sistema SHALL configurar `REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES']` con `IsAuthenticated` como permiso por defecto, de modo que todos los endpoints requieran autenticación a menos que se indique explícitamente lo contrario.
3. THE Sistema SHALL configurar `REST_FRAMEWORK['DEFAULT_SCHEMA_CLASS']` con `AutoSchema` de drf-spectacular para la generación automática del esquema OpenAPI.
4. THE Sistema SHALL configurar `SIMPLE_JWT['ACCESS_TOKEN_LIFETIME']` en 8 horas (`timedelta(hours=8)`).
5. THE Sistema SHALL configurar `SIMPLE_JWT['REFRESH_TOKEN_LIFETIME']` en 7 días (`timedelta(days=7)`).
6. THE Sistema SHALL configurar `CORS_ALLOWED_ORIGINS` leyendo el valor de la variable de entorno `CORS_ALLOWED_ORIGINS` con valor por defecto `http://localhost:5173`.
7. THE Sistema SHALL incluir `corsheaders.middleware.CorsMiddleware` en `MIDDLEWARE` antes de `CommonMiddleware`.
8. THE Sistema SHALL incluir `corsheaders`, `rest_framework`, `rest_framework_simplejwt`, `drf_spectacular` en `INSTALLED_APPS`.

### Requisito 6: Registro de URLs de autenticación

**Historia de usuario:** Como desarrollador del sistema, quiero que las rutas `/api/auth/login/` y `/api/auth/refresh/` estén registradas en el router de URLs, para que los endpoints sean accesibles desde el frontend.

#### Criterios de aceptación

1. THE Sistema SHALL incluir las URLs de la app `cuentas` bajo el prefijo `/api/auth/` en `config/urls.py`.
2. THE Sistema SHALL mapear `POST /api/auth/login/` a la `LoginView` custom.
3. THE Sistema SHALL mapear `POST /api/auth/refresh/` al `TokenRefreshView` de SimpleJWT.
4. THE Sistema SHALL registrar el endpoint `GET /api/schema/` de drf-spectacular en `config/urls.py` para servir el esquema OpenAPI en formato YAML/JSON.

### Requisito 7: Fixtures de usuarios de prueba

**Historia de usuario:** Como desarrollador del equipo, quiero que exista un archivo de fixtures con un usuario por cada rol, para poder levantar un entorno de desarrollo con datos de prueba ejecutando un solo comando `loaddata`.

#### Criterios de aceptación

1. THE Sistema SHALL proveer el archivo `api/fixtures/usuarios_prueba.json` con exactamente 5 usuarios, uno por cada rol: `superadmin`, `dueno`, `rrpp`, `guardia`, `cajera`.
2. WHEN un desarrollador ejecuta `python manage.py loaddata usuarios_prueba`, THE Sistema SHALL cargar los 5 usuarios en la base de datos sin errores.
3. THE Sistema SHALL incluir para cada usuario en el fixture los campos `username`, `password` (hasheada con el algoritmo de Django), `first_name`, `last_name`, `rol` y `is_staff` (verdadero solo para el superadmin).
4. THE Sistema SHALL asignar contraseñas predecibles y documentadas a los usuarios del fixture para facilitar el acceso en desarrollo.

### Requisito 8: Tests de autenticación y permisos

**Historia de usuario:** Como desarrollador del sistema, quiero que exista una suite de tests en `apps/cuentas/tests.py` que verifique el correcto funcionamiento del login, los tokens y los permisos custom, para detectar regresiones durante el desarrollo.

#### Criterios de aceptación

1. THE Sistema SHALL incluir un test que verifique que `POST /api/auth/login/` con credenciales correctas devuelve HTTP 200 con los campos `access`, `refresh`, `rol`, `nombre` e `id`.
2. THE Sistema SHALL incluir un test que verifique que `POST /api/auth/login/` con credenciales incorrectas devuelve HTTP 401.
3. THE Sistema SHALL incluir un test que verifique que un endpoint protegido con `IsDueno` sin token devuelve HTTP 401 o HTTP 403.
4. THE Sistema SHALL incluir un test que verifique que un endpoint protegido con `IsDueno` con un token de usuario con `rol=rrpp` devuelve HTTP 403.
5. THE Sistema SHALL incluir un test que verifique que un endpoint protegido con `IsDueno` con un token de usuario con `rol=dueno` devuelve HTTP 200.
6. THE Sistema SHALL incluir un test por cada clase de permiso (`IsSuperAdmin`, `IsDueno`, `IsRRPP`, `IsGuardia`, `IsCajera`) que verifique que solo el rol correcto obtiene acceso.
7. THE Sistema SHALL incluir un test que verifique que un access token expirado devuelve HTTP 401.
8. THE Sistema SHALL incluir un test que verifique que el payload del JWT contiene el campo `rol` con el valor correcto del usuario.
