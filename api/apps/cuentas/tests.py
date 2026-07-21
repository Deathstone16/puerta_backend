"""
Tests de la app `cuentas` — autenticación, JWT y permisos por rol.

Cubre los requisitos 8.1 al 8.8 del spec.
"""
from datetime import timedelta

from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import path, reverse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIClient, APITestCase
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from .models import Usuario
from .permissions import IsCajera, IsDueno, IsGuardia, IsRRPP, IsSuperAdmin


# ─── Vistas de prueba para tests de permisos ─────────────────────────────────

class _VistaProtegidaDueno(APIView):
    permission_classes = [IsDueno]

    def get(self, request):
        return Response({'ok': True})


class _VistaProtegidaRRPP(APIView):
    permission_classes = [IsRRPP]

    def get(self, request):
        return Response({'ok': True})


class _VistaProtegidaGuardia(APIView):
    permission_classes = [IsGuardia]

    def get(self, request):
        return Response({'ok': True})


class _VistaProtegidaCajera(APIView):
    permission_classes = [IsCajera]

    def get(self, request):
        return Response({'ok': True})


class _VistaProtegidaSuperAdmin(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        return Response({'ok': True})


# URLs de prueba inyectadas via override_settings
_test_urlpatterns = [
    path('api/auth/', __import__('django.urls', fromlist=['include']).include('apps.cuentas.urls')),
    path('test/dueno/',      _VistaProtegidaDueno.as_view()),
    path('test/rrpp/',       _VistaProtegidaRRPP.as_view()),
    path('test/guardia/',    _VistaProtegidaGuardia.as_view()),
    path('test/cajera/',     _VistaProtegidaCajera.as_view()),
    path('test/superadmin/', _VistaProtegidaSuperAdmin.as_view()),
    path('admin/', __import__('django.contrib.admin', fromlist=['site']).site.urls),
]


# ─── Helper ──────────────────────────────────────────────────────────────────

def _crear_usuario(username, password, rol, **kwargs):
    """Crea un usuario de prueba con el rol indicado."""
    u = Usuario.objects.create_user(
        username=username,
        password=password,
        rol=rol,
        first_name=kwargs.get('first_name', ''),
        last_name=kwargs.get('last_name', ''),
    )
    return u


# ─── Tests de modelo ─────────────────────────────────────────────────────────

class UsuarioModelTests(TestCase):

    def test_modelo_tiene_campo_rol(self):
        """El modelo Usuario tiene el campo 'rol' con 5 choices."""
        campo = Usuario._meta.get_field('rol')
        choices_valores = [c[0] for c in campo.choices]
        self.assertIn('superadmin', choices_valores)
        self.assertIn('dueno', choices_valores)
        self.assertIn('rrpp', choices_valores)
        self.assertIn('guardia', choices_valores)
        self.assertIn('cajera', choices_valores)

    def test_modelo_tiene_campo_telefono_opcional(self):
        """El campo 'telefono' acepta None."""
        u = _crear_usuario('u1', 'pass1234', 'dueno')
        self.assertIsNone(u.telefono)

    def test_str_incluye_rol(self):
        """__str__ muestra username y rol display."""
        u = _crear_usuario('u2', 'pass1234', 'guardia')
        self.assertIn('u2', str(u))
        self.assertIn('Guardia', str(u))

    def test_usuario_sin_rol_falla_full_clean(self):
        """Crear Usuario sin rol falla la validación del modelo."""
        from django.core.exceptions import ValidationError
        u = Usuario(username='sinrol', rol='')
        u.set_password('pass1234')
        with self.assertRaises(ValidationError):
            u.full_clean()

    def test_auth_user_model_es_cuentas_usuario(self):
        """AUTH_USER_MODEL apunta a cuentas.Usuario."""
        from django.conf import settings
        self.assertEqual(settings.AUTH_USER_MODEL, 'cuentas.Usuario')


# ─── Tests de autenticación ──────────────────────────────────────────────────

@override_settings(
    ROOT_URLCONF=__name__ + '._test_url_module',
    REST_FRAMEWORK={
        'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework_simplejwt.authentication.JWTAuthentication'],
        'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
        'DEFAULT_THROTTLE_CLASSES': [],
        'DEFAULT_THROTTLE_RATES': {'login': '1000/min', 'anon': '1000/min', 'user': '1000/min'},
    },
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}},
)
class AuthTests(APITestCase):
    """Tests de los endpoints de login y refresh."""

    def setUp(self):
        # Parchear ROOT_URLCONF para usar nuestras URLs de prueba
        import sys
        import types
        mod = types.ModuleType(__name__ + '._test_url_module')
        mod.urlpatterns = _test_urlpatterns
        sys.modules[__name__ + '._test_url_module'] = mod

        self.client = APIClient()
        self.usuario = _crear_usuario(
            'testuser', 'testpass1234', 'dueno',
            first_name='Juan', last_name='Pérez',
        )
        self.login_url   = '/api/auth/login/'
        self.refresh_url = '/api/auth/refresh/'

    def test_login_exitoso_devuelve_tokens_y_datos(self):
        """Login con credenciales correctas → 200 con access, refresh, rol, nombre, id."""
        resp = self.client.post(self.login_url, {
            'username': 'testuser',
            'password': 'testpass1234',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('access',  resp.data)
        self.assertIn('refresh', resp.data)
        self.assertIn('rol',     resp.data)
        self.assertIn('nombre',  resp.data)
        self.assertIn('id',      resp.data)
        self.assertEqual(resp.data['rol'], 'dueno')
        self.assertEqual(resp.data['nombre'], 'Juan Pérez')
        self.assertEqual(resp.data['id'], self.usuario.id)

    def test_login_con_credenciales_incorrectas_devuelve_401(self):
        """Login con password incorrecta → 401."""
        resp = self.client.post(self.login_url, {
            'username': 'testuser',
            'password': 'wrongpassword',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_sin_username_devuelve_400(self):
        """Login sin campo username → 400."""
        resp = self.client.post(self.login_url, {
            'password': 'testpass1234',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_sin_password_devuelve_400(self):
        """Login sin campo password → 400."""
        resp = self.client.post(self.login_url, {
            'username': 'testuser',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_jwt_contiene_claim_rol(self):
        """El payload del JWT tiene el claim 'rol' con el valor correcto."""
        resp = self.client.post(self.login_url, {
            'username': 'testuser',
            'password': 'testpass1234',
        }, format='json')
        token = AccessToken(resp.data['access'])
        self.assertEqual(token['rol'], 'dueno')

    def test_refresh_token_valido_devuelve_nuevo_access(self):
        """POST /refresh/ con refresh válido → 200 con nuevo access token."""
        login_resp = self.client.post(self.login_url, {
            'username': 'testuser',
            'password': 'testpass1234',
        }, format='json')
        self.assertEqual(login_resp.status_code, status.HTTP_200_OK, f"Login failed: {login_resp.data}")
        refresh_token = login_resp.data['refresh']
        resp = self.client.post(self.refresh_url, {
            'refresh': refresh_token,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('access', resp.data)

    def test_refresh_token_invalido_devuelve_401(self):
        """POST /refresh/ con refresh malformado → 401."""
        resp = self.client.post(self.refresh_url, {
            'refresh': 'token.invalido.aqui',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_nombre_fallback_a_username_cuando_no_hay_nombre(self):
        """Si first_name y last_name están vacíos, nombre = username."""
        _crear_usuario('sinnombre', 'pass1234', 'guardia')
        resp = self.client.post(self.login_url, {
            'username': 'sinnombre',
            'password': 'pass1234',
        }, format='json')
        self.assertEqual(resp.data['nombre'], 'sinnombre')


# ─── Tests de permisos ───────────────────────────────────────────────────────

@override_settings(ROOT_URLCONF=__name__ + '._test_url_module')
class PermisosTests(APITestCase):
    """Tests de las clases de permiso por rol."""

    def setUp(self):
        import sys
        import types
        mod = types.ModuleType(__name__ + '._test_url_module')
        mod.urlpatterns = _test_urlpatterns
        sys.modules[__name__ + '._test_url_module'] = mod

        self.client = APIClient()
        # Crear un usuario por cada rol
        self.usuarios = {
            rol: _crear_usuario(f'user_{rol}', f'pass_{rol}1234', rol)
            for rol in ['superadmin', 'dueno', 'rrpp', 'guardia', 'cajera']
        }

    def _token_para(self, rol):
        token = AccessToken.for_user(self.usuarios[rol])
        # Agregar claim personalizado
        token['rol'] = rol
        return str(token)

    def _get(self, url, rol=None):
        self.client.credentials()
        if rol:
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self._token_para(rol)}')
        return self.client.get(url)

    def test_endpoint_sin_token_devuelve_401(self):
        """Sin token → 401."""
        resp = self._get('/test/dueno/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_dueno_accede_a_vista_dueno(self):
        """Token con rol=dueno → 200 en vista IsDueno."""
        resp = self._get('/test/dueno/', rol='dueno')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_rrpp_no_accede_a_vista_dueno(self):
        """Token con rol=rrpp → 403 en vista IsDueno."""
        resp = self._get('/test/dueno/', rol='rrpp')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_guardia_no_accede_a_vista_dueno(self):
        """Token con rol=guardia → 403 en vista IsDueno."""
        resp = self._get('/test/dueno/', rol='guardia')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_rrpp_accede_a_vista_rrpp(self):
        """Token con rol=rrpp → 200 en vista IsRRPP."""
        resp = self._get('/test/rrpp/', rol='rrpp')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_guardia_accede_a_vista_guardia(self):
        """Token con rol=guardia → 200 en vista IsGuardia."""
        resp = self._get('/test/guardia/', rol='guardia')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_cajera_accede_a_vista_cajera(self):
        """Token con rol=cajera → 200 en vista IsCajera."""
        resp = self._get('/test/cajera/', rol='cajera')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_superadmin_accede_a_vista_superadmin(self):
        """Token con rol=superadmin → 200 en vista IsSuperAdmin."""
        resp = self._get('/test/superadmin/', rol='superadmin')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_cada_rol_solo_accede_a_su_vista(self):
        """Cada rol solo accede a su vista y es rechazado en las demás."""
        vistas = {
            'dueno':      '/test/dueno/',
            'rrpp':       '/test/rrpp/',
            'guardia':    '/test/guardia/',
            'cajera':     '/test/cajera/',
            'superadmin': '/test/superadmin/',
        }
        for rol_usuario, url_propia in vistas.items():
            for rol_vista, url in vistas.items():
                resp = self._get(url, rol=rol_usuario)
                if rol_usuario == rol_vista:
                    self.assertEqual(
                        resp.status_code, status.HTTP_200_OK,
                        f"Rol '{rol_usuario}' debería acceder a {url}"
                    )
                else:
                    self.assertEqual(
                        resp.status_code, status.HTTP_403_FORBIDDEN,
                        f"Rol '{rol_usuario}' NO debería acceder a {url}"
                    )


# ─── Tests de fixtures ───────────────────────────────────────────────────────

class FixtureTests(TestCase):

    def test_fixtures_usuarios_prueba_cargan_correctamente(self):
        """loaddata usuarios_prueba carga exactamente 5 usuarios, uno por rol."""
        call_command('loaddata', 'usuarios_prueba', verbosity=0)
        self.assertEqual(Usuario.objects.count(), 5)
        roles_esperados = {'superadmin', 'dueno', 'rrpp', 'guardia', 'cajera'}
        roles_cargados = set(Usuario.objects.values_list('rol', flat=True))
        self.assertEqual(roles_cargados, roles_esperados)

    def test_fixture_contrasenas_son_validas(self):
        """Los usuarios del fixture tienen contraseñas funcionales."""
        call_command('loaddata', 'usuarios_prueba', verbosity=0)
        credenciales = [
            ('admin',         'admin123'),
            ('carlos_dueno',  'dueno123'),
            ('juan_rrpp',     'rrpp123'),
            ('maria_guardia', 'guardia123'),
            ('ana_cajera',    'cajera123'),
        ]
        for username, password in credenciales:
            u = Usuario.objects.get(username=username)
            self.assertTrue(
                u.check_password(password),
                f"Contraseña inválida para {username}"
            )
