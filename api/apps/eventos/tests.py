"""
Tests de la app `eventos` — cálculo de precios, CRUD, cancelación.
"""
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.boliches.models import Boliche
from apps.cuentas.models import Usuario

from .models import Evento
from .utils import calcular_precio_publicado


# ─── Helpers ─────────────────────────────────────────────────────────────────

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


def _crear_boliche(dueno):
    return Boliche.objects.create(
        nombre='Club Test', direccion='Calle 1', dueno=dueno,
    )


def _crear_evento(boliche, **kwargs):
    defaults = {
        'nombre': 'Noche Techno',
        'fecha': timezone.now() + timezone.timedelta(days=7),
        'aforo_max': 800,
        'color_pulsera': 'violeta',
        'precio_base': Decimal('5000.00'),
        'line_up': [{'artista': 'DJ Test', 'horario': '00:00'}],
    }
    defaults.update(kwargs)
    return Evento.objects.create(boliche=boliche, **defaults)


# ─── Tests de utils.calcular_precio_publicado ────────────────────────────────

class CalcularPrecioTests(TestCase):

    def test_calcular_precio_con_fees_default(self):
        """Con precio_base=10000, FEE_MP=5.99%, NORWARE=8% → 11399."""
        result = calcular_precio_publicado(10000)
        self.assertEqual(result['precio_base'], 10000)
        self.assertAlmostEqual(result['fee_mp'], 599.00, places=2)
        self.assertAlmostEqual(result['fee_norware'], 800.00, places=2)
        self.assertEqual(result['precio_publicado'], 11399)

    def test_calcular_precio_con_5000(self):
        """Con precio_base=5000 → desglose correcto."""
        result = calcular_precio_publicado(5000)
        self.assertEqual(result['precio_base'], 5000)
        self.assertAlmostEqual(result['fee_mp'], 299.50, places=2)
        self.assertAlmostEqual(result['fee_norware'], 400.00, places=2)
        self.assertEqual(result['precio_publicado'], 5700)

    def test_calcular_precio_base_cero_lanza_value_error(self):
        with self.assertRaises(ValueError):
            calcular_precio_publicado(0)

    def test_calcular_precio_base_negativo_lanza_value_error(self):
        with self.assertRaises(ValueError):
            calcular_precio_publicado(-100)

    def test_calcular_precio_base_no_numerico_lanza_value_error(self):
        with self.assertRaises(ValueError):
            calcular_precio_publicado('abc')

    @override_settings(FEE_MP_PCT=10.0, NORWARE_FEE_PCT=5.0)
    def test_calcular_precio_lee_fees_de_settings(self):
        """Verifica que usa los fees del settings."""
        result = calcular_precio_publicado(1000)
        # fee_mp = 1000 * 10% = 100, fee_norware = 1000 * 5% = 50
        self.assertAlmostEqual(result['fee_mp'], 100.0, places=2)
        self.assertAlmostEqual(result['fee_norware'], 50.0, places=2)
        self.assertEqual(result['precio_publicado'], 1150)


# ─── Tests del listado público ───────────────────────────────────────────────

class EventoListTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.dueno = _crear_usuario('dueno1', 'dueno')
        self.boliche = _crear_boliche(self.dueno)
        self.evento_activo = _crear_evento(self.boliche, nombre='Activo')
        self.evento_cancelado = _crear_evento(
            self.boliche, nombre='Cancelado', estado='cancelado',
            motivo_cancelacion='Motivo test',
        )

    def test_listado_publico_sin_auth(self):
        resp = self.client.get('/api/eventos/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_listado_filtra_por_estado_activo(self):
        resp = self.client.get('/api/eventos/?estado=activo')
        nombres = [e['nombre'] for e in resp.data]
        self.assertIn('Activo', nombres)
        self.assertNotIn('Cancelado', nombres)

    def test_listado_filtra_por_estado_cancelado(self):
        resp = self.client.get('/api/eventos/?estado=cancelado')
        nombres = [e['nombre'] for e in resp.data]
        self.assertIn('Cancelado', nombres)
        self.assertNotIn('Activo', nombres)

    def test_listado_sin_filtro_trae_todos(self):
        resp = self.client.get('/api/eventos/')
        self.assertEqual(len(resp.data), 2)

    def test_listado_incluye_precio_publicado(self):
        resp = self.client.get('/api/eventos/')
        self.assertIn('precio_publicado', resp.data[0])

    def test_listado_incluye_boliche_anidado(self):
        resp = self.client.get('/api/eventos/')
        self.assertIn('boliche', resp.data[0])
        self.assertIn('nombre', resp.data[0]['boliche'])


# ─── Tests del detalle ───────────────────────────────────────────────────────

class EventoDetailTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.dueno = _crear_usuario('dueno2', 'dueno')
        self.boliche = _crear_boliche(self.dueno)
        self.evento = _crear_evento(self.boliche)

    def test_detalle_incluye_desglose_precio(self):
        resp = self.client.get(f'/api/eventos/{self.evento.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('desglose_precio', resp.data)
        self.assertIn('fee_mp', resp.data['desglose_precio'])
        self.assertIn('fee_norware', resp.data['desglose_precio'])
        self.assertIn('precio_publicado', resp.data['desglose_precio'])

    def test_detalle_incluye_line_up(self):
        resp = self.client.get(f'/api/eventos/{self.evento.pk}/')
        self.assertIn('line_up', resp.data)
        self.assertEqual(len(resp.data['line_up']), 1)

    def test_detalle_evento_inexistente_devuelve_404(self):
        resp = self.client.get('/api/eventos/9999/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_devuelve_405(self):
        resp = self.client.delete(f'/api/eventos/{self.evento.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


# ─── Tests de creación ───────────────────────────────────────────────────────

class EventoCreateTests(TestCase):

    def setUp(self):
        self.dueno = _crear_usuario('dueno3', 'dueno')
        self.boliche = _crear_boliche(self.dueno)
        self.client = _auth_client(self.dueno)
        self.payload = {
            'boliche_id': self.boliche.pk,
            'nombre': 'Nueva Noche',
            'fecha': '2026-08-05T23:00:00-03:00',
            'aforo_max': 1200,
            'color_pulsera': 'roja',
            'precio_base': '7000.00',
            'line_up': [{'artista': 'Test', 'horario': '01:00'}],
        }

    def test_crear_evento_como_dueno(self):
        resp = self.client.post('/api/eventos/crear/', self.payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('precio_publicado', resp.data)
        self.assertIn('desglose_precio', resp.data)
        self.assertEqual(resp.data['nombre'], 'Nueva Noche')

    def test_crear_evento_boliche_ajeno_devuelve_403(self):
        otro_dueno = _crear_usuario('otro_dueno', 'dueno')
        client = _auth_client(otro_dueno)
        resp = client.post('/api/eventos/crear/', self.payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_crear_evento_sin_auth_devuelve_401(self):
        client = APIClient()
        resp = client.post('/api/eventos/crear/', self.payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_crear_evento_campos_faltantes_devuelve_400(self):
        del self.payload['nombre']
        resp = self.client.post('/api/eventos/crear/', self.payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ─── Tests de edición (PATCH) ────────────────────────────────────────────────

class EventoPatchTests(TestCase):

    def setUp(self):
        self.dueno = _crear_usuario('dueno4', 'dueno')
        self.boliche = _crear_boliche(self.dueno)
        self.evento = _crear_evento(self.boliche)
        self.client = _auth_client(self.dueno)
        self.url = f'/api/eventos/{self.evento.pk}/'

    def test_patch_evento_activo_exitoso(self):
        resp = self.client.patch(self.url, {'nombre': 'Editado'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['nombre'], 'Editado')

    def test_patch_evento_cancelado_devuelve_405(self):
        self.evento.estado = 'cancelado'
        self.evento.motivo_cancelacion = 'Test'
        self.evento.save()
        resp = self.client.patch(self.url, {'nombre': 'X'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_patch_evento_de_otro_dueno_devuelve_403(self):
        otro = _crear_usuario('otro5', 'dueno')
        client = _auth_client(otro)
        resp = client.patch(self.url, {'nombre': 'Hack'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_patch_sin_auth_devuelve_403(self):
        """Sin token, DRF deja pasar al GET (AllowAny) pero PATCH verifica rol manualmente."""
        client = APIClient()
        resp = client.patch(self.url, {'nombre': 'X'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ─── Tests de cancelación ────────────────────────────────────────────────────

class EventoCancelarTests(TestCase):

    def setUp(self):
        self.dueno = _crear_usuario('dueno5', 'dueno')
        self.boliche = _crear_boliche(self.dueno)
        self.evento = _crear_evento(self.boliche)
        self.client = _auth_client(self.dueno)
        self.url = f'/api/eventos/{self.evento.pk}/cancelar/'

    def test_cancelar_evento_exitoso(self):
        resp = self.client.post(self.url, {'motivo': 'Lluvia'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['estado'], 'cancelado')
        self.assertEqual(resp.data['motivo_cancelacion'], 'Lluvia')
        self.assertIn('reembolsos_iniciados', resp.data)
        self.evento.refresh_from_db()
        self.assertEqual(self.evento.estado, 'cancelado')

    def test_cancelar_sin_motivo_devuelve_400(self):
        resp = self.client.post(self.url, {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancelar_motivo_solo_espacios_devuelve_400(self):
        resp = self.client.post(self.url, {'motivo': '   '}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancelar_evento_ya_cancelado_devuelve_409(self):
        self.evento.estado = 'cancelado'
        self.evento.motivo_cancelacion = 'Ya'
        self.evento.save()
        resp = self.client.post(self.url, {'motivo': 'Otra'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_cancelar_evento_de_otro_dueno_devuelve_403(self):
        otro = _crear_usuario('otro6', 'dueno')
        client = _auth_client(otro)
        resp = client.post(self.url, {'motivo': 'Hack'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_cancelar_evento_inexistente_devuelve_404(self):
        resp = self.client.post('/api/eventos/9999/cancelar/', {'motivo': 'X'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_cancelar_sin_pagos_disponibles_devuelve_cero_reembolsos(self):
        """Sin apps.pagos, reembolsos_iniciados = 0."""
        resp = self.client.post(self.url, {'motivo': 'Test'}, format='json')
        self.assertEqual(resp.data['reembolsos_iniciados'], 0)

    def test_patch_evento_cancelado_despues_de_cancelar_devuelve_405(self):
        self.client.post(self.url, {'motivo': 'Test'}, format='json')
        resp = self.client.patch(f'/api/eventos/{self.evento.pk}/', {'nombre': 'X'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


# ─── Tests de calculadora de precios ─────────────────────────────────────────

class CalcularPrecioEndpointTests(TestCase):

    def setUp(self):
        self.client = APIClient()

    def test_calcular_precio_endpoint_exitoso(self):
        resp = self.client.get('/api/precios/calcular/?precio_base=5000')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['precio_base'], 5000)
        self.assertEqual(resp.data['precio_publicado'], 5700)

    def test_calcular_precio_sin_param_devuelve_400(self):
        resp = self.client.get('/api/precios/calcular/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_calcular_precio_no_numerico_devuelve_400(self):
        resp = self.client.get('/api/precios/calcular/?precio_base=abc')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_calcular_precio_cero_devuelve_400(self):
        resp = self.client.get('/api/precios/calcular/?precio_base=0')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_calcular_precio_sin_auth_permitido(self):
        """Endpoint público, sin token → 200."""
        resp = self.client.get('/api/precios/calcular/?precio_base=1000')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
