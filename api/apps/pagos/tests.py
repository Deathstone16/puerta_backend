"""
Tests de la app `pagos` — preferencia MP, webhook, wallet, reembolsos, dashboards.
Todos los tests mockean el SDK de MP.
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.boliches.models import Boliche
from apps.cuentas.models import Usuario
from apps.eventos.models import Evento
from apps.puerta.models import Asistente
from apps.rrpp.models import AsignacionRRPP, RRPP


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _crear_usuario(username, rol, password='testpass1234', **kwargs):
    return Usuario.objects.create_user(username=username, password=password, rol=rol, **kwargs)


def _token(user):
    t = AccessToken.for_user(user)
    t['rol'] = user.rol
    return str(t)


def _auth_client(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(user)}')
    return c


def _setup():
    dueno = _crear_usuario('dueno_pago', 'dueno')
    boliche = Boliche.objects.create(
        nombre='Club', direccion='Dir', dueno=dueno,
        mp_access_token='TEST-seller-token', mp_user_id='12345',
    )
    evento = Evento.objects.create(
        boliche=boliche, nombre='Noche', fecha=timezone.now() + timezone.timedelta(days=3),
        aforo_max=500, color_pulsera='violeta', precio_base=Decimal('5000'),
    )
    return dueno, boliche, evento


# ─── Tests de Preferencia ────────────────────────────────────────────────────

class PreferenciaTests(TestCase):

    def setUp(self):
        self.dueno, self.boliche, self.evento = _setup()
        self.client = APIClient()
        self.payload = {
            'evento_id': self.evento.pk,
            'nombre': 'María',
            'apellido': 'López',
            'dni': '38123456',
            'email': 'maria@test.com',
        }

    @patch('apps.pagos.mp_client._get_seller_sdk')
    def test_preferencia_exitosa(self, mock_sdk):
        mock_pref = MagicMock()
        mock_pref.create.return_value = {
            'status': 201,
            'response': {'init_point': 'https://mp.com/checkout', 'id': 'pref-123'},
        }
        mock_sdk.return_value.preference.return_value = mock_pref

        resp = self.client.post('/api/pagos/preferencia/', self.payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('init_point', resp.data)
        self.assertIn('preference_id', resp.data)
        self.assertIn('desglose', resp.data)

    def test_preferencia_evento_cancelado_devuelve_400(self):
        self.evento.estado = 'cancelado'
        self.evento.motivo_cancelacion = 'X'
        self.evento.save()
        resp = self.client.post('/api/pagos/preferencia/', self.payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_preferencia_dni_duplicado_devuelve_409(self):
        Asistente.objects.create(
            evento=self.evento, nombre='X', apellido='Y', dni='38123456',
            tipo_ingreso='web_anticipada', estado='aprobado_guardia',
        )
        resp = self.client.post('/api/pagos/preferencia/', self.payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_preferencia_campos_faltantes_devuelve_400(self):
        del self.payload['email']
        resp = self.client.post('/api/pagos/preferencia/', self.payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('apps.pagos.mp_client._get_seller_sdk')
    def test_preferencia_mp_error_devuelve_503(self, mock_sdk):
        mock_pref = MagicMock()
        mock_pref.create.return_value = {'status': 500, 'response': {}}
        mock_sdk.return_value.preference.return_value = mock_pref

        resp = self.client.post('/api/pagos/preferencia/', self.payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)


# ─── Tests de Webhook ────────────────────────────────────────────────────────

class WebhookTests(TestCase):

    def setUp(self):
        _, _, self.evento = _setup()
        self.client = APIClient()

    @patch('apps.pagos.mp_client.obtener_pago')
    def test_webhook_pago_aprobado_crea_asistente(self, mock_obtener):
        mock_obtener.return_value = {
            'status': 'approved',
            'metadata': {
                'evento_id': self.evento.pk,
                'dni': '40000001',
                'nombre': 'Test',
                'apellido': 'User',
            },
            'payer': {'email': 'test@test.com', 'first_name': 'T', 'last_name': 'U'},
            'transaction_amount': 5700,
            'fee_details': [{'amount': 400}],
        }
        resp = self.client.post('/api/pagos/webhook/', {
            'type': 'payment',
            'data': {'id': 'PAY-001'},
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        a = Asistente.objects.get(mp_payment_id='PAY-001')
        self.assertEqual(a.estado, 'aprobado_guardia')
        self.assertEqual(a.tipo_ingreso, 'web_anticipada')
        self.assertEqual(a.mp_fee_norware, 400)

    @patch('apps.pagos.mp_client.obtener_pago')
    def test_webhook_idempotente_no_duplica(self, mock_obtener):
        Asistente.objects.create(
            evento=self.evento, nombre='X', apellido='Y', dni='40000002',
            tipo_ingreso='web_anticipada', estado='aprobado_guardia',
            mp_payment_id='PAY-DUP',
        )
        resp = self.client.post('/api/pagos/webhook/', {
            'type': 'payment',
            'data': {'id': 'PAY-DUP'},
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(Asistente.objects.filter(mp_payment_id='PAY-DUP').count(), 1)
        mock_obtener.assert_not_called()

    def test_webhook_tipo_no_payment_ignorado(self):
        resp = self.client.post('/api/pagos/webhook/', {
            'type': 'merchant_order',
            'data': {'id': 'ORD-001'},
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(Asistente.objects.count(), 0)

    @patch('apps.pagos.mp_client.obtener_pago')
    def test_webhook_pago_no_approved_no_crea(self, mock_obtener):
        mock_obtener.return_value = {'status': 'pending', 'metadata': {}}
        resp = self.client.post('/api/pagos/webhook/', {
            'type': 'payment',
            'data': {'id': 'PAY-PEND'},
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(Asistente.objects.filter(mp_payment_id='PAY-PEND').exists())

    @patch('apps.pagos.mp_client.obtener_pago')
    def test_webhook_siempre_responde_200(self, mock_obtener):
        mock_obtener.side_effect = Exception("boom")
        resp = self.client.post('/api/pagos/webhook/', {
            'type': 'payment',
            'data': {'id': 'PAY-ERR'},
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


# ─── Tests de Wallet ─────────────────────────────────────────────────────────

class WalletTests(TestCase):

    def setUp(self):
        _, _, self.evento = _setup()
        self.asistente = Asistente.objects.create(
            evento=self.evento, nombre='María', apellido='López', dni='50000001',
            tipo_ingreso='web_anticipada', estado='aprobado_guardia',
        )
        self.client = APIClient()

    def test_wallet_devuelve_datos_completos(self):
        resp = self.client.get(f'/api/wallet/{self.asistente.wallet_token}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['nombre'], 'María')
        self.assertEqual(resp.data['qr_code'], str(self.asistente.wallet_token))
        self.assertIn('evento', resp.data)
        self.assertEqual(resp.data['evento']['color_pulsera'], 'violeta')
        self.assertFalse(resp.data['evento_cancelado'])

    def test_wallet_token_inexistente_devuelve_404(self):
        import uuid
        resp = self.client.get(f'/api/wallet/{uuid.uuid4()}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_wallet_evento_cancelado_incluye_motivo(self):
        self.evento.estado = 'cancelado'
        self.evento.motivo_cancelacion = 'Lluvia fuerte'
        self.evento.save()
        resp = self.client.get(f'/api/wallet/{self.asistente.wallet_token}/')
        self.assertTrue(resp.data['evento_cancelado'])
        self.assertEqual(resp.data['motivo_cancelacion'], 'Lluvia fuerte')


# ─── Tests de Reembolsos ─────────────────────────────────────────────────────

class ReembolsoTests(TestCase):

    def setUp(self):
        _, _, self.evento = _setup()

    @patch('apps.pagos.services.reembolsar_pago')
    def test_reembolsar_evento_llama_mp(self, mock_reembolso):
        mock_reembolso.return_value = True
        for i in range(3):
            Asistente.objects.create(
                evento=self.evento, nombre='X', apellido='Y', dni=f'6000000{i}',
                tipo_ingreso='web_anticipada', estado='aprobado_guardia',
                mp_payment_id=f'PAY-{i}',
            )
        from apps.pagos.services import reembolsar_evento
        result = reembolsar_evento(self.evento.id)
        self.assertEqual(result, 3)
        self.assertEqual(mock_reembolso.call_count, 3)

    @patch('apps.pagos.services.reembolsar_pago')
    def test_reembolsar_evento_idempotency_key_correcta(self, mock_reembolso):
        mock_reembolso.return_value = True
        a = Asistente.objects.create(
            evento=self.evento, nombre='X', apellido='Y', dni='60000010',
            tipo_ingreso='web_anticipada', estado='aprobado_guardia',
            mp_payment_id='PAY-KEY',
        )
        from apps.pagos.services import reembolsar_evento
        reembolsar_evento(self.evento.id)
        mock_reembolso.assert_called_once_with(
            payment_id='PAY-KEY',
            idempotency_key=f'refund-{a.id}',
        )

    @patch('apps.pagos.services.reembolsar_pago')
    def test_reembolsar_evento_continua_si_uno_falla(self, mock_reembolso):
        from apps.pagos.mp_client import MPError
        mock_reembolso.side_effect = [MPError("fail"), True]
        for i in range(2):
            Asistente.objects.create(
                evento=self.evento, nombre='X', apellido='Y', dni=f'7000000{i}',
                tipo_ingreso='web_anticipada', estado='aprobado_guardia',
                mp_payment_id=f'PAY-F{i}',
            )
        from apps.pagos.services import reembolsar_evento
        result = reembolsar_evento(self.evento.id)
        self.assertEqual(result, 1)  # uno falló, uno ok

    def test_reembolsar_evento_sin_asistentes_web_devuelve_cero(self):
        from apps.pagos.services import reembolsar_evento
        result = reembolsar_evento(self.evento.id)
        self.assertEqual(result, 0)


# ─── Tests de Recaudación ────────────────────────────────────────────────────

class RecaudacionTests(TestCase):

    def setUp(self):
        self.dueno, self.boliche, self.evento = _setup()
        self.client = _auth_client(self.dueno)
        # Crear asistentes ingresados con distintos métodos
        Asistente.objects.create(
            evento=self.evento, nombre='A', apellido='B', dni='80000001',
            tipo_ingreso='web_anticipada', estado='ingresado_final',
            metodo_pago='ya_pago_web', monto_pagado=5700, mp_fee_norware=400,
            ingresado_at=timezone.now(),
        )
        Asistente.objects.create(
            evento=self.evento, nombre='C', apellido='D', dni='80000002',
            tipo_ingreso='lista_rrpp', estado='ingresado_final',
            metodo_pago='efectivo', monto_pagado=5700,
            ingresado_at=timezone.now(),
        )
        Asistente.objects.create(
            evento=self.evento, nombre='E', apellido='F', dni='80000003',
            tipo_ingreso='lista_rrpp', estado='ingresado_final',
            metodo_pago='transferencia', monto_pagado=5700,
            ingresado_at=timezone.now(),
        )

    def test_recaudacion_desglose_correcto(self):
        resp = self.client.get(f'/api/dashboard/recaudacion/{self.evento.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['web']['cantidad'], 1)
        self.assertEqual(resp.data['efectivo']['cantidad'], 1)
        self.assertEqual(resp.data['transferencia']['cantidad'], 1)
        self.assertEqual(resp.data['total_recaudado'], 17100.0)
        self.assertEqual(resp.data['comision_norware_web'], 400.0)

    def test_recaudacion_evento_ajeno_devuelve_403(self):
        otro = _crear_usuario('otro_dueno_p', 'dueno')
        client = _auth_client(otro)
        resp = client.get(f'/api/dashboard/recaudacion/{self.evento.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ─── Tests de Métricas Admin ─────────────────────────────────────────────────

class MetricasAdminTests(TestCase):

    def setUp(self):
        self.superadmin = _crear_usuario('superadmin_p', 'superadmin')
        _, _, self.evento = _setup()
        Asistente.objects.create(
            evento=self.evento, nombre='X', apellido='Y', dni='90000001',
            tipo_ingreso='web_anticipada', estado='aprobado_guardia',
            mp_payment_id='PAY-M1', mp_fee_norware=400, monto_pagado=5700,
        )

    def test_metricas_accesible_por_superadmin(self):
        client = _auth_client(self.superadmin)
        resp = client.get('/api/admin/metricas/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('totales', resp.data)
        self.assertIn('por_evento', resp.data)
        self.assertEqual(resp.data['totales']['entradas_web_total'], 1)

    def test_metricas_rechaza_dueno(self):
        dueno = _crear_usuario('dueno_noadmin', 'dueno')
        client = _auth_client(dueno)
        resp = client.get('/api/admin/metricas/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
