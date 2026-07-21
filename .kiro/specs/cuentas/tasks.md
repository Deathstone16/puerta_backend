# Plan de implementación: `cuentas` — Auth, Usuarios y Roles

## Resumen

Implementación incremental de la app `cuentas` de Norware: modelo de usuario con roles, permisos DRF custom, endpoints de autenticación JWT, configuración de settings, fixtures de prueba y suite de tests completa.

Cada tarea construye sobre la anterior. Al final todos los componentes quedan conectados y testeados.

**Lenguaje:** Python 3.x | **Framework:** Django 6 + DRF + SimpleJWT

---

## Tareas

- [ ] 1. Modelo `Usuario` — agregar campo `rol` y migración
  - Editar `apps/cuentas/models.py`: agregar campo `rol` (CharField, max_length=20, choices=ROLES, sin default) con las 5 opciones: `superadmin`, `dueno`, `rrpp`, `guardia`, `cajera`
  - Verificar que el campo `telefono` ya existente sigue siendo `blank=True, null=True`
  - Actualizar `__str__` para incluir el rol: `f"{self.username} ({self.get_rol_display()})"`
  - Crear migración: `python manage.py makemigrations cuentas` (nombrarla `0002_usuario_add_rol`)
  - La migración debe manejar la transición: agregar `rol` como nullable temporalmente, asignar `superadmin` a superusers y `dueno` al resto via `RunPython`, luego hacerlo not-nullable
  - _Requisitos: 1.1, 1.2, 1.3, 1.4, 1.6_

  - [ ]* 1.1 Tests unitarios del modelo
    - Verificar que `Usuario` tiene el campo `rol` con las 5 choices correctas
    - Verificar que crear un usuario sin `rol` falla la validación de modelo
    - Verificar que `telefono` acepta `None` y cadena vacía
    - Verificar que `AUTH_USER_MODEL == 'cuentas.Usuario'` en settings
    - _Requisitos: 1.2, 1.3, 1.4, 1.5_

- [ ] 2. Configuración de settings — DRF, SimpleJWT, CORS, drf-spectacular
  - Editar `config/settings.py`:
    - Agregar a `INSTALLED_APPS`: `'corsheaders'`, `'rest_framework'`, `'rest_framework_simplejwt'`, `'drf_spectacular'`
    - Agregar `'corsheaders.middleware.CorsMiddleware'` en `MIDDLEWARE` inmediatamente antes de `'django.middleware.common.CommonMiddleware'`
    - Agregar bloque `REST_FRAMEWORK` con `JWTAuthentication`, `IsAuthenticated` y `AutoSchema`
    - Agregar bloque `SIMPLE_JWT` con `ACCESS_TOKEN_LIFETIME=timedelta(hours=8)` y `REFRESH_TOKEN_LIFETIME=timedelta(days=7)` (importar `timedelta` desde `datetime`)
    - Agregar `CORS_ALLOWED_ORIGINS` leyendo de variable de entorno con `python-decouple`: `config('CORS_ALLOWED_ORIGINS', default='http://localhost:5173').split(',')`
    - Agregar bloque `SPECTACULAR_SETTINGS` con título, descripción y versión
    - Importar `config` desde `decouple` al inicio del archivo
  - _Requisitos: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_

- [ ] 3. Permisos custom basados en rol
  - Crear `apps/cuentas/permissions.py` con 5 clases: `IsSuperAdmin`, `IsDueno`, `IsRRPP`, `IsGuardia`, `IsCajera`
  - Cada clase extiende `BasePermission` de DRF
  - `has_permission` verifica `request.user.is_authenticated and request.user.rol == '{rol}'`
  - _Requisitos: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

  - [ ]* 3.1 Property test: permisos verifican el rol correcto
    - Instalar `hypothesis` si no está en `requirements.txt`
    - Crear `apps/cuentas/tests_properties.py`
    - Implementar generador `@st.composite` que cree usuarios con roles aleatorios de los 5 válidos
    - Crear vista de prueba `VistaProtegidaDueno(APIView)` con `permission_classes = [IsDueno]` en el módulo de tests
    - **Property 1: Permisos de rol verifican correctamente el rol del usuario**
    - Para cualquier usuario con rol `R` y cualquier clase `PermisoRol_req`, `has_permission()` debe retornar `True` si y solo si `R == rol_requerido`
    - Mínimo 100 ejemplos
    - Tag: `# Feature: cuentas, Property 1: Permisos de rol verifican correctamente el rol del usuario`
    - _Requisitos: 2.2, 2.3, 2.4, 2.5, 2.6_

- [ ] 4. Serializer custom y vista de login
  - Crear `apps/cuentas/serializers.py` con `CustomTokenObtainPairSerializer(TokenObtainPairSerializer)`:
    - Sobrescribir `get_token(cls, user)`: llamar a `super().get_token(user)`, agregar `token['rol'] = user.rol` y retornar el token
    - Sobrescribir `validate(self, attrs)`: llamar a `super().validate(attrs)`, agregar al dict resultado: `data['rol']`, `data['nombre']` (concatenación de first_name + last_name, con fallback a username si ambos están vacíos), `data['id']`
  - Editar `apps/cuentas/views.py`: crear `LoginView(TokenObtainPairView)` que use `CustomTokenObtainPairSerializer`
  - _Requisitos: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_

  - [ ]* 4.1 Property test: respuesta de login contiene el rol correcto
    - En `apps/cuentas/tests_properties.py` agregar test
    - Generador: crear usuario con rol aleatorio de los 5 válidos, conocer su password en texto plano
    - POST a `/api/auth/login/` con credenciales del usuario generado
    - Verificar que `response.data['rol'] == usuario.rol`
    - Verificar que `response.data['id'] == usuario.id`
    - Mínimo 100 ejemplos
    - Tag: `# Feature: cuentas, Property 2: La respuesta de login contiene el rol correcto`
    - **Property 2: La respuesta de login contiene el rol correcto**
    - _Requisitos: 3.2, 3.3, 3.4, 3.5_

  - [ ]* 4.2 Property test: JWT contiene el claim de rol correcto
    - En `apps/cuentas/tests_properties.py` agregar test
    - Generador: mismo que 4.1
    - Después del login exitoso, decodificar el access token con `AccessToken(token_str)` de SimpleJWT
    - Verificar que `decoded_token['rol'] == usuario.rol`
    - Mínimo 100 ejemplos
    - Tag: `# Feature: cuentas, Property 3: El JWT contiene el claim de rol correcto`
    - **Property 3: El JWT contiene el claim de rol correcto**
    - _Requisitos: 3.8_

- [ ] 5. URLs de la app `cuentas` y registro en config

  - [ ] 5.1 Crear URLs de la app
    - Crear `apps/cuentas/urls.py` con dos rutas:
      - `path('login/', LoginView.as_view(), name='login')`
      - `path('refresh/', TokenRefreshView.as_view(), name='token_refresh')`
    - Importar `TokenRefreshView` de `rest_framework_simplejwt.views` y `LoginView` de `.views`
    - _Requisitos: 6.1, 6.2, 6.3_

  - [ ] 5.2 Registrar URLs en config
    - Editar `config/urls.py`:
      - Agregar `include` a los imports de `django.urls`
      - Registrar `path('api/auth/', include('apps.cuentas.urls'))`
      - Registrar `path('api/schema/', SpectacularAPIView.as_view(), name='schema')` (importar de `drf_spectacular.views`)
    - _Requisitos: 6.1, 6.4_

- [ ] 6. Checkpoint — Verificar funcionamiento básico
  - Ejecutar `python manage.py migrate` para aplicar la migración del campo `rol`
  - Ejecutar `python manage.py check` para verificar que no hay errores de configuración
  - Ejecutar `python manage.py test apps.cuentas` para correr los tests escritos hasta aquí
  - Asegurarse de que todos los tests pasan. Consultar al usuario si surgen dudas.

- [ ] 7. Admin de Django para `Usuario`
  - Editar `apps/cuentas/admin.py`:
    - Importar `UserAdmin` de `django.contrib.auth.admin`
    - Crear `UsuarioAdmin(UserAdmin)` con:
      - `list_display = ['username', 'rol', 'first_name', 'last_name', 'is_staff', 'is_active']`
      - `list_filter = ['rol', 'is_staff', 'is_superuser', 'is_active']`
      - `fieldsets = UserAdmin.fieldsets + (('Rol y Contacto', {'fields': ('rol', 'telefono')}),)`
      - `add_fieldsets = UserAdmin.add_fieldsets + (('Rol y Contacto', {'fields': ('rol', 'telefono')}),)`
    - Decorar con `@admin.register(Usuario)`
  - _Requisitos: 1.1_

- [ ] 8. Fixtures de usuarios de prueba
  - Crear directorio `api/fixtures/` si no existe
  - Crear `api/fixtures/usuarios_prueba.json` con 5 usuarios, uno por rol: `superadmin`, `dueno`, `rrpp`, `guardia`, `cajera`
  - Usar el helper de Django `make_password` para hashear contraseñas:
    - `admin` / `admin123` / rol `superadmin` / `is_staff: true` / `is_superuser: true`
    - `carlos_dueno` / `dueno123` / rol `dueno` / `is_staff: false`
    - `juan_rrpp` / `rrpp123` / rol `rrpp` / `is_staff: false`
    - `maria_guardia` / `guardia123` / rol `guardia` / `is_staff: false`
    - `ana_cajera` / `cajera123` / rol `cajera` / `is_staff: false`
  - Formato: `[{"model": "cuentas.usuario", "pk": N, "fields": {...}}]`
  - Verificar que `python manage.py loaddata usuarios_prueba` carga correctamente sin errores
  - _Requisitos: 7.1, 7.2, 7.3, 7.4_

  - [ ]* 8.1 Test de carga de fixtures
    - En `apps/cuentas/tests.py` agregar `test_fixtures_usuarios_prueba_cargan_correctamente`
    - Usar `call_command('loaddata', 'usuarios_prueba')` y verificar que se crean exactamente 5 usuarios
    - Verificar que hay exactamente un usuario por cada rol
    - _Requisitos: 7.1, 7.2_

- [ ] 9. Suite de tests unitarios completa en `apps/cuentas/tests.py`
  - Implementar los siguientes tests usando `TestCase` de Django y `APIClient` de DRF:
    - `test_login_exitoso_devuelve_tokens_y_datos`: POST a `/api/auth/login/` con usuario válido, verificar 200 y campos `access`, `refresh`, `rol`, `nombre`, `id`
    - `test_login_con_credenciales_incorrectas_devuelve_401`: POST con password incorrecta, verificar 401
    - `test_login_sin_username_devuelve_400`: POST sin campo `username`, verificar 400
    - `test_refresh_token_valido_devuelve_nuevo_access`: POST a `/api/auth/refresh/` con refresh válido, verificar 200 y campo `access`
    - `test_refresh_token_invalido_devuelve_401`: POST con refresh mal formado, verificar 401
    - `test_refresh_token_expirado_devuelve_401`: crear RefreshToken con lifetime muy pequeño, esperar expiración, verificar 401
    - `test_endpoint_protegido_sin_token_devuelve_401`: GET a endpoint protegido sin header, verificar 401
    - `test_endpoint_con_rol_correcto_devuelve_200`: autenticar como `dueno`, acceder a endpoint `IsDueno`, verificar 200
    - `test_endpoint_con_rol_incorrecto_devuelve_403`: autenticar como `rrpp`, acceder a endpoint `IsDueno`, verificar 403
    - `test_usuario_sin_rol_falla_full_clean`: crear Usuario sin rol, llamar `full_clean()`, verificar `ValidationError`
  - Para crear la vista de prueba usada en tests de permisos, definirla como función anónima en `setUp` o como clase interna del TestCase usando `override_settings` para las URLs
  - _Requisitos: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

- [ ] 10. Checkpoint final — Suite completa de tests pasa
  - Ejecutar `python manage.py test apps.cuentas` y verificar que todos los tests unitarios pasan
  - Ejecutar `python manage.py test apps.cuentas.tests_properties` para los property tests
  - Ejecutar `python manage.py check --deploy` para verificar warnings de seguridad (ignorar los relacionados con SSL en desarrollo)
  - Verificar que el endpoint `/api/schema/` responde correctamente
  - Asegurarse de que todos los tests pasan. Consultar al usuario si surgen dudas.

---

## Notas

- Las tareas marcadas con `*` son opcionales y pueden omitirse para acelerar el MVP.
- Cada tarea referencia requisitos específicos del documento de requisitos para trazabilidad.
- Los checkpoints en tareas 6 y 10 validan el progreso incremental.
- La suite de property tests requiere agregar `hypothesis` a `requirements.txt` con versión pinned: `hypothesis==6.135.26` (o la versión más reciente estable al momento de implementar).
- Las fixtures usan `make_password` de Django — las contraseñas se documentan en texto plano en este documento pero se almacenan hasheadas en el JSON.
