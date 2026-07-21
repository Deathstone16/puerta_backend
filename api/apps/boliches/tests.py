"""
Tests de la app `boliches` — CRUD + OAuth Mercado Pago Marketplace.
"""
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.cuentas.models import Usuario

from .models import Boliche


def _crear_usuario(username, rol, password='testpass1234'):
    return Usuario.objects.create_user(username=username, password=password, rol=rol)


def _token(user):
    token = AccessToken.for_user(user)
    token['rol'] = user.rol
    return str(token)


def _auth_client(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(user)}')
    return client


class BolicheModelTests(TestCase):

    def test_mp_connected_false_sin_token(self):
        dueno = _crear_usuario('d1', 'dueno')
        b = Boliche.objects.create(nombre='Club', direccion='Dir', dueno=dueno)
        self.assertFalse(b.mp_connected)

    def test_mp_connected_true_con_token_y_user_id(self):
        dueno = _crear_usuario('d2', 'dueno')
        b = Boliche.objects.create(
            nombre='Club', direccion='Dir', dueno=dueno,
            mp_access_token='TOKEN', mp_user_id='12345',
        )
        self.assertTrue(b.mp_connected)

    def test_str_incluye_nombre_y_dueno(self):
        dueno = _crear_usuario('d3', 'dueno')
        b = Boliche.objects.create(nombre='Club X', direccion='Dir', dueno=dueno)
        self.assertIn('Club X', str(b))
        self.assertIn('d3', str(b))


class CrearBolicheTests(TestCase):

    def setUp(self):
        self.dueno = _crear_usuario('dueno1', 'dueno')
        self.client = _auth_client(self.dueno)
        self.payload = {'nombre': 'Club Crobar', 'direccion': 'Av. Figueroa Alcorta 3657'}

    def test_crear_boliche_exitoso(self):
        resp = self.client.post('/api/boliches/', self.payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['nombre'], 'Club Crobar')
        self.assertIn('mp_connected', resp.data)
        self.assertFalse(resp.data['mp_connected'])
        self.assertNotIn('dueno', resp.data)

    def test_crear_boliche_sin_nombre_devuelve_400(self):
        del self.payload['nombre']
        resp = self.client.post('/api/boliches/', self.payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_crear_segundo_boliche_devuelve_409(self):
        self.client.post('/api/boliches/', self.payload, format='json')
        resp = self.client.post('/api/boliches/', self.payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_crear_boliche_sin_auth_devuelve_401(self):
        client = APIClient()
        resp = client.post('/api/boliches/', self.payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_crear_boliche_rol_incorrecto_devuelve_403(self):
        guardia = _crear_usuario('guardia1', 'guardia')
        client = _auth_client(guardia)
        resp = client.post('/api/boliches/', self.payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class ObtenerMiBolicheTests(TestCase):

    def setUp(self):
        self.dueno = _crear_usuario('dueno2', 'dueno')
        self.client = _auth_client(self.dueno)

    def test_obtener_mi_boliche_exitoso(self):
        Boliche.objects.create(nombre='Mi Club', direccion='Calle 1', dueno=self.dueno)
        resp = self.client.get('/api/boliches/mio/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['nombre'], 'Mi Club')
        self.assertIn('mp_connected', resp.data)

    def test_obtener_mi_boliche_sin_boliche_devuelve_404(self):
        resp = self.client.get('/api/boliches/mio/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class PatchBolicheTests(TestCase):

    def setUp(self):
        self.dueno = _crear_usuario('dueno3', 'dueno')
        self.boliche = Boliche.objects.create(nombre='Original', direccion='Dir 1', dueno=self.dueno)
        self.client = _auth_client(self.dueno)
        self.url = f'/api/boliches/{self.boliche.pk}/'

    def test_patch_boliche_exitoso(self):
        resp = self.client.patch(self.url, {'nombre': 'Editado'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['nombre'], 'Editado')

    def test_patch_boliche_de_otro_dueno_devuelve_403(self):
        otro = _crear_usuario('dueno4', 'dueno')
        client = _auth_client(otro)
        resp = client.patch(self.url, {'nombre': 'Hack'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_patch_boliche_inexistente_devuelve_404(self):
        resp = self.client.patch('/api/boliches/9999/', {'nombre': 'X'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_devuelve_405(self):
        resp = self.client.delete(self.url)
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class MPConnectTests(TestCase):

    def setUp(self):
        self.dueno = _crear_usuario('dueno5', 'dueno')
        self.client = _auth_client(self.dueno)

    @override_settings(MP_APP_ID='APP-123', MP_REDIRECT_URI='http://localhost:8000/api/boliches/mp/callback/')
    def test_connect_devuelve_auth_url(self):
        Boliche.objects.create(nombre='Club', direccion='Dir', dueno=self.dueno)
        resp = self.client.get('/api/boliches/mp/connect/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('auth_url', resp.data)
        self.assertIn('auth.mercadopago.com.ar', resp.data['auth_url'])
        self.assertIn('APP-123', resp.data['auth_url'])

    def test_connect_sin_boliche_devuelve_400(self):
        resp = self.client.get('/api/boliches/mp/connect/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_connect_sin_auth_devuelve_401(self):
        client = APIClient()
        resp = client.get('/api/boliches/mp/connect/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class MPCallbackTests(TestCase):

    def setUp(self):
        self.dueno = _crear_usuario('dueno6', 'dueno')
        self.boliche = Boliche.objects.create(nombre='Club', direccion='Dir', dueno=self.dueno)
        self.client = APIClient()

    @patch('apps.boliches.views._exchange_code_for_token')
    @override_settings(FRONTEND_URL='http://localhost:5173')
    def test_callback_exitoso_guarda_tokens(self, mock_exchange):
        mock_exchange.return_value = {
            'access_token': 'APP_USR-seller-token',
            'refresh_token': 'TG-seller-refresh',
            'user_id': 987654321,
            'expires_in': 15552000,
        }
        resp = self.client.get('/api/boliches/mp/callback/', {
            'code': 'TG-test-code',
            'state': str(self.dueno.id),
        })
        # Redirige al frontend con éxito
        self.assertEqual(resp.status_code, 302)
        self.assertIn('mp_connected=true', resp.url)

        # Verificar que se guardaron los datos
        self.boliche.refresh_from_db()
        self.assertEqual(self.boliche.mp_access_token, 'APP_USR-seller-token')
        self.assertEqual(self.boliche.mp_refresh_token, 'TG-seller-refresh')
        self.assertEqual(self.boliche.mp_user_id, '987654321')
        self.assertTrue(self.boliche.mp_connected)
        self.assertIsNotNone(self.boliche.mp_connected_at)

    @patch('apps.boliches.views._exchange_code_for_token')
    @override_settings(FRONTEND_URL='http://localhost:5173')
    def test_callback_error_redirige_con_error(self, mock_exchange):
        from apps.boliches.views import MPOAuthError
        mock_exchange.side_effect = MPOAuthError("bad code")
        resp = self.client.get('/api/boliches/mp/callback/', {
            'code': 'bad-code',
            'state': str(self.dueno.id),
        })
        self.assertEqual(resp.status_code, 302)
        self.assertIn('mp_error=true', resp.url)

    def test_callback_sin_code_devuelve_400(self):
        resp = self.client.get('/api/boliches/mp/callback/', {'state': '1'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
