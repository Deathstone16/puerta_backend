"""
Tests de la app `puerta` — flujo guardia, cajera, aforo, lista pública.
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.boliches.models import Boliche
from apps.cuentas.models import Usuario
from apps.eventos.models import Evento
from apps.rrpp.models import AsignacionRRPP, LinkRRPP, RRPP

from .models import Asistente


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


def _setup_evento():
    """Crea dueño + boliche + evento + guardia + cajera + rrpp con asignación."""
    dueno = _crear_usuario('dueno_p', 'dueno')
    boliche = Boliche.objects.create(
        nombre='Club', direccion='Dir', dueno=dueno,
    )
    evento = Evento.objects.create(
        boliche=boliche, nombre='Noche', fecha=timezone.now() + timedelta(days=3),
        aforo_max=100, color_pulsera='violeta', precio_base=Decimal('5000'),
    )
    guardia = _crear_usuario('guardia_p', 'guardia')
    cajera = _crear_usuario('cajera_p', 'cajera')
    rrpp_user = _crear_usuario('rrpp_p', 'rrpp', first_name='Juan', last_name='P')
    rrpp = RRPP.objects.create(
        usuario=rrpp_user, boliche=boliche, tipo_comision='fijo', valor_comision=500,
    )
    asignacion = AsignacionRRPP.objects.create(rrpp=rrpp, evento=evento)
    link_lista = asignacion.links.get(tipo='lista')
    return evento, guardia, cajera, link_lista


def _anotar(evento, link, dni='12345678', nombre='Test', apellido='User'):
    return Asistente.objects.create(
        evento=evento, link_rrpp=link, nombre=nombre, apellido=apellido,
        dni=dni, tipo_ingreso='lista_rrpp', estado='pendiente',
    )


# ─── Tests de lista pública ──────────────────────────────────────────────────

class ListaPublicaTests(TestCase):

    def setUp(self):
        self.evento, _, _, self.link = _setup_evento()
        self.client = APIClient()

    def test_get_info_lista_exitoso(self):
        resp = self.client.get(f'/api/lista/{self.link.slug}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('evento', resp.data)
        self.assertEqual(resp.data['anotados'], 0)

    def test_get_info_lista_inexistente_devuelve_404(self):
        import uuid
        resp = self.client.get(f'/api/lista/{uuid.uuid4()}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_info_lista_inactiva_devuelve_410(self):
        self.link.activo = False
        self.link.save()
        resp = self.client.get(f'/api/lista/{self.link.slug}/')
        self.assertEqual(resp.status_code, status.HTTP_410_GONE)

    def test_anotar_exitoso(self):
        resp = self.client.post(f'/api/lista/{self.link.slug}/anotar/', {
            'nombre': 'María', 'apellido': 'López', 'dni': '33333333',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['estado'], 'pendiente')

    def test_anotar_dni_duplicado_devuelve_409(self):
        _anotar(self.evento, self.link, dni='44444444')
        resp = self.client.post(f'/api/lista/{self.link.slug}/anotar/', {
            'nombre': 'Otro', 'apellido': 'X', 'dni': '44444444',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_anotar_link_inactivo_devuelve_410(self):
        self.link.activo = False
        self.link.save()
        resp = self.client.post(f'/api/lista/{self.link.slug}/anotar/', {
            'nombre': 'X', 'apellido': 'Y', 'dni': '55555555',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_410_GONE)

    def test_anotar_campos_faltantes_devuelve_400(self):
        resp = self.client.post(f'/api/lista/{self.link.slug}/anotar/', {
            'nombre': 'Solo',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_anotar_evento_cancelado_devuelve_423(self):
        self.evento.estado = 'cancelado'
        self.evento.motivo_cancelacion = 'Test'
        self.evento.save()
        resp = self.client.post(f'/api/lista/{self.link.slug}/anotar/', {
            'nombre': 'X', 'apellido': 'Y', 'dni': '66666666',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_423_LOCKED)


# ─── Tests de Guardia ────────────────────────────────────────────────────────

class GuardiaTests(TestCase):

    def setUp(self):
        self.evento, self.guardia, _, self.link = _setup_evento()
        self.client = _auth_client(self.guardia)
        self.asistente = _anotar(self.evento, self.link)

    def test_escanear_por_dni_exitoso(self):
        resp = self.client.post('/api/puerta/guardia/escanear/', {
            'dni': self.asistente.dni, 'evento_id': self.evento.pk,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['id'], self.asistente.pk)

    def test_escanear_por_qr_exitoso(self):
        resp = self.client.post('/api/puerta/guardia/escanear/', {
            'qr_code': str(self.asistente.wallet_token),
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_escanear_no_encontrado_devuelve_404(self):
        resp = self.client.post('/api/puerta/guardia/escanear/', {
            'dni': '99999999', 'evento_id': self.evento.pk,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_aprobar_pendiente_exitoso(self):
        resp = self.client.post(f'/api/puerta/guardia/aprobar/{self.asistente.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['estado'], 'aprobado_guardia')
        self.asistente.refresh_from_db()
        self.assertEqual(self.asistente.estado, 'aprobado_guardia')
        self.assertIsNotNone(self.asistente.aprobado_at)

    def test_aprobar_no_pendiente_devuelve_400(self):
        self.asistente.estado = 'aprobado_guardia'
        self.asistente.save()
        resp = self.client.post(f'/api/puerta/guardia/aprobar/{self.asistente.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rebotar_con_motivo_exitoso(self):
        resp = self.client.post(f'/api/puerta/guardia/rebotar/{self.asistente.pk}/', {
            'motivo': 'Dress code',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['estado'], 'rebotado_guardia')

    def test_rebotar_sin_motivo_devuelve_400(self):
        resp = self.client.post(f'/api/puerta/guardia/rebotar/{self.asistente.pk}/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_guardia_evento_cancelado_devuelve_423(self):
        self.evento.estado = 'cancelado'
        self.evento.motivo_cancelacion = 'Test'
        self.evento.save()
        resp = self.client.post(f'/api/puerta/guardia/aprobar/{self.asistente.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_423_LOCKED)


# ─── Tests de Cajera ─────────────────────────────────────────────────────────

class CajeraTests(TestCase):

    def setUp(self):
        self.evento, _, self.cajera, self.link = _setup_evento()
        self.client = _auth_client(self.cajera)

    def _crear_asistente_aprobado(self, tipo='lista_rrpp', dni='77777777'):
        a = Asistente.objects.create(
            evento=self.evento, link_rrpp=self.link, nombre='X', apellido='Y',
            dni=dni, tipo_ingreso=tipo, estado='aprobado_guardia',
            aprobado_at=timezone.now(),
        )
        return a

    def test_escanear_web_exitoso(self):
        a = self._crear_asistente_aprobado(tipo='web_anticipada', dni='88888888')
        resp = self.client.post(f'/api/puerta/cajera/escanear-web/{a.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['estado'], 'ingresado_final')
        self.assertIn('color_pulsera', resp.data)

    def test_escanear_web_sin_guardia_devuelve_409(self):
        a = Asistente.objects.create(
            evento=self.evento, nombre='X', apellido='Y', dni='11111111',
            tipo_ingreso='web_anticipada', estado='pendiente',
        )
        resp = self.client.post(f'/api/puerta/cajera/escanear-web/{a.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_cobrar_lista_exitoso(self):
        a = self._crear_asistente_aprobado()
        resp = self.client.post(f'/api/puerta/cajera/cobrar-lista/{a.pk}/', {
            'metodo_pago': 'efectivo', 'monto_pagado': 5700,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['estado'], 'ingresado_final')
        self.assertIn('color_pulsera', resp.data)

    def test_cobrar_lista_sin_guardia_devuelve_409(self):
        a = Asistente.objects.create(
            evento=self.evento, nombre='X', apellido='Y', dni='22222222',
            tipo_ingreso='lista_rrpp', estado='pendiente',
        )
        resp = self.client.post(f'/api/puerta/cajera/cobrar-lista/{a.pk}/', {
            'metodo_pago': 'efectivo', 'monto_pagado': 5700,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_cajera_evento_cancelado_devuelve_423(self):
        a = self._crear_asistente_aprobado(dni='33333333')
        self.evento.estado = 'cancelado'
        self.evento.motivo_cancelacion = 'Test'
        self.evento.save()
        resp = self.client.post(f'/api/puerta/cajera/cobrar-lista/{a.pk}/', {
            'metodo_pago': 'efectivo', 'monto_pagado': 5700,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_423_LOCKED)

    def test_venta_general_crea_asistentes(self):
        resp = self.client.post('/api/puerta/cajera/venta-general/', {
            'evento_id': self.evento.pk,
            'personas': [
                {'nombre': 'A', 'apellido': 'B', 'dni': '40000001', 'metodo_pago': 'efectivo'},
                {'nombre': 'C', 'apellido': 'D', 'dni': '40000002', 'metodo_pago': 'transferencia'},
            ],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['creados'], 2)
        self.assertIn('color_pulsera', resp.data)

    def test_venta_general_dni_duplicado_en_evento_devuelve_409(self):
        _anotar(self.evento, self.link, dni='50000001')
        resp = self.client.post('/api/puerta/cajera/venta-general/', {
            'evento_id': self.evento.pk,
            'personas': [
                {'nombre': 'X', 'apellido': 'Y', 'dni': '50000001', 'metodo_pago': 'efectivo'},
            ],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_rebotado_no_llega_a_cajera(self):
        """Un rebotado nunca puede ser procesado por la cajera."""
        a = Asistente.objects.create(
            evento=self.evento, nombre='X', apellido='Y', dni='60000001',
            tipo_ingreso='lista_rrpp', estado='rebotado_guardia',
            rebotado_at=timezone.now(),
        )
        resp = self.client.post(f'/api/puerta/cajera/cobrar-lista/{a.pk}/', {
            'metodo_pago': 'efectivo', 'monto_pagado': 5700,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)


# ─── Tests de Deshacer ───────────────────────────────────────────────────────

class DeshacerTests(TestCase):

    def setUp(self):
        self.evento, _, self.cajera, self.link = _setup_evento()
        self.client = _auth_client(self.cajera)

    def test_deshacer_dentro_ventana_exitoso(self):
        a = Asistente.objects.create(
            evento=self.evento, nombre='X', apellido='Y', dni='70000001',
            tipo_ingreso='lista_rrpp', estado='ingresado_final',
            metodo_pago='efectivo', monto_pagado=5700,
            ingresado_at=timezone.now() - timedelta(minutes=5),
        )
        resp = self.client.post(f'/api/puerta/cajera/deshacer/{a.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        a.refresh_from_db()
        self.assertEqual(a.estado, 'aprobado_guardia')
        self.assertIsNone(a.ingresado_at)
        self.assertIsNone(a.metodo_pago)

    def test_deshacer_fuera_ventana_devuelve_403(self):
        a = Asistente.objects.create(
            evento=self.evento, nombre='X', apellido='Y', dni='70000002',
            tipo_ingreso='lista_rrpp', estado='ingresado_final',
            metodo_pago='efectivo', monto_pagado=5700,
            ingresado_at=timezone.now() - timedelta(minutes=15),
        )
        resp = self.client.post(f'/api/puerta/cajera/deshacer/{a.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_deshacer_no_ingresado_devuelve_400(self):
        a = Asistente.objects.create(
            evento=self.evento, nombre='X', apellido='Y', dni='70000003',
            tipo_ingreso='lista_rrpp', estado='aprobado_guardia',
        )
        resp = self.client.post(f'/api/puerta/cajera/deshacer/{a.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ─── Tests de Aforo ──────────────────────────────────────────────────────────

class AforoTests(TestCase):

    def setUp(self):
        self.evento, self.guardia, self.cajera, self.link = _setup_evento()

    def test_aforo_calcula_correctamente(self):
        # Crear 3 ingresados
        for i in range(3):
            Asistente.objects.create(
                evento=self.evento, nombre='X', apellido='Y', dni=f'8000000{i}',
                tipo_ingreso='venta_general', estado='ingresado_final',
                ingresado_at=timezone.now(),
            )
        # 1 pendiente
        Asistente.objects.create(
            evento=self.evento, nombre='P', apellido='P', dni='80000009',
            tipo_ingreso='lista_rrpp', estado='pendiente',
        )
        client = _auth_client(self.guardia)
        resp = client.get(f'/api/dashboard/aforo/{self.evento.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['ingresados'], 3)
        self.assertEqual(resp.data['aforo_max'], 100)
        self.assertEqual(resp.data['porcentaje'], 3.0)
        self.assertEqual(resp.data['pendientes'], 1)

    def test_aforo_accesible_por_cajera(self):
        client = _auth_client(self.cajera)
        resp = client.get(f'/api/dashboard/aforo/{self.evento.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_aforo_evento_inexistente_devuelve_404(self):
        client = _auth_client(self.guardia)
        resp = client.get('/api/dashboard/aforo/9999/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


# ─── Test de flujo completo ──────────────────────────────────────────────────

class FlujoCompletoTests(TestCase):
    """Test end-to-end: anotar → guardia aprueba → cajera cobra → aforo +1."""

    def test_flujo_lista_completo(self):
        evento, guardia, cajera, link = _setup_evento()
        client_pub = APIClient()
        client_g = _auth_client(guardia)
        client_c = _auth_client(cajera)

        # 1. Anotar público
        resp = client_pub.post(f'/api/lista/{link.slug}/anotar/', {
            'nombre': 'Test', 'apellido': 'Flow', 'dni': '99000001',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        asistente_id = resp.data['id']

        # 2. Guardia escanea
        resp = client_g.post('/api/puerta/guardia/escanear/', {
            'dni': '99000001', 'evento_id': evento.pk,
        }, format='json')
        self.assertEqual(resp.data['estado'], 'pendiente')

        # 3. Guardia aprueba
        resp = client_g.post(f'/api/puerta/guardia/aprobar/{asistente_id}/')
        self.assertEqual(resp.data['estado'], 'aprobado_guardia')

        # 4. Cajera cobra
        resp = client_c.post(f'/api/puerta/cajera/cobrar-lista/{asistente_id}/', {
            'metodo_pago': 'efectivo', 'monto_pagado': 5700,
        }, format='json')
        self.assertEqual(resp.data['estado'], 'ingresado_final')

        # 5. Aforo sube
        resp = client_g.get(f'/api/dashboard/aforo/{evento.pk}/')
        self.assertEqual(resp.data['ingresados'], 1)
