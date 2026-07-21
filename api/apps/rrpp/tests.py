"""
Tests de la app `rrpp` — alta, asignación, signal de links, panel y anotación.
"""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.boliches.models import Boliche
from apps.cuentas.models import Usuario
from apps.eventos.models import Evento

from .models import AsignacionRRPP, LinkRRPP, RRPP


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _crear_usuario(username, rol, password='testpass1234', **kwargs):
    return Usuario.objects.create_user(
        username=username, password=password, rol=rol, **kwargs,
    )


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
    }
    defaults.update(kwargs)
    return Evento.objects.create(boliche=boliche, **defaults)


def _crear_rrpp(boliche, username='rrpp1'):
    user = _crear_usuario(username, 'rrpp', first_name='Juan', last_name='Pérez')
    return RRPP.objects.create(
        usuario=user, boliche=boliche,
        tipo_comision='fijo', valor_comision=Decimal('500.00'),
    )


# ─── Tests de alta de RRPP ───────────────────────────────────────────────────

class AltaRRPPTests(TestCase):

    def setUp(self):
        self.dueno = _crear_usuario('dueno1', 'dueno')
        self.boliche = _crear_boliche(self.dueno)
        self.client = _auth_client(self.dueno)
        self.payload = {
            'nombre': 'Juan',
            'apellido': 'Pérez',
            'username': 'nuevo_rrpp',
            'password': 'pass1234',
            'telefono': '1123456789',
            'tipo_comision': 'fijo',
            'valor_comision': '500.00',
        }

    def test_alta_rrpp_exitosa_crea_usuario_y_perfil(self):
        resp = self.client.post('/api/rrpp/', self.payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', resp.data)
        self.assertEqual(resp.data['nombre'], 'Juan Pérez')
        # Verificar que se creó usuario con rol rrpp
        user = Usuario.objects.get(username='nuevo_rrpp')
        self.assertEqual(user.rol, 'rrpp')
        # Verificar perfil RRPP
        self.assertTrue(hasattr(user, 'perfil_rrpp'))
        self.assertEqual(user.perfil_rrpp.boliche, self.boliche)

    def test_alta_rrpp_username_duplicado_revierte_transaction(self):
        _crear_usuario('existente', 'rrpp')
        self.payload['username'] = 'existente'
        resp = self.client.post('/api/rrpp/', self.payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        # No se creó RRPP huérfano
        self.assertEqual(RRPP.objects.count(), 0)

    def test_alta_rrpp_campos_faltantes_devuelve_400(self):
        del self.payload['username']
        resp = self.client.post('/api/rrpp/', self.payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_alta_rrpp_sin_auth_devuelve_401(self):
        client = APIClient()
        resp = client.post('/api/rrpp/', self.payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_alta_rrpp_rol_incorrecto_devuelve_403(self):
        guardia = _crear_usuario('guardia1', 'guardia')
        client = _auth_client(guardia)
        resp = client.post('/api/rrpp/', self.payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_listado_rrpp_solo_muestra_los_del_boliche_propio(self):
        _crear_rrpp(self.boliche, username='rrpp_propio')
        # Crear otro dueño con otro boliche y otro RRPP
        otro_dueno = _crear_usuario('otro_dueno', 'dueno')
        otro_boliche = Boliche.objects.create(
            nombre='Otro Club', direccion='X', dueno=otro_dueno,
        )
        _crear_rrpp(otro_boliche, username='rrpp_ajeno')

        resp = self.client.get('/api/rrpp/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        usernames = [r['username'] for r in resp.data]
        self.assertIn('rrpp_propio', usernames)
        self.assertNotIn('rrpp_ajeno', usernames)


# ─── Tests de signal de links ────────────────────────────────────────────────

class SignalLinksTests(TestCase):

    def setUp(self):
        self.dueno = _crear_usuario('dueno2', 'dueno')
        self.boliche = _crear_boliche(self.dueno)
        self.rrpp = _crear_rrpp(self.boliche, username='rrpp2')
        self.evento = _crear_evento(self.boliche)

    def test_asignacion_nueva_genera_exactamente_2_links(self):
        asignacion = AsignacionRRPP.objects.create(rrpp=self.rrpp, evento=self.evento)
        self.assertEqual(asignacion.links.count(), 2)

    def test_asignacion_nueva_genera_un_lista_y_un_venta_web(self):
        asignacion = AsignacionRRPP.objects.create(rrpp=self.rrpp, evento=self.evento)
        tipos = set(asignacion.links.values_list('tipo', flat=True))
        self.assertEqual(tipos, {'lista', 'venta_web'})

    def test_signal_no_crea_links_en_update(self):
        asignacion = AsignacionRRPP.objects.create(rrpp=self.rrpp, evento=self.evento)
        self.assertEqual(asignacion.links.count(), 2)
        # Save de nuevo (update) no crea más links
        asignacion.activa = False
        asignacion.save()
        self.assertEqual(asignacion.links.count(), 2)

    def test_slugs_son_uuid_unicos(self):
        asignacion = AsignacionRRPP.objects.create(rrpp=self.rrpp, evento=self.evento)
        slugs = list(asignacion.links.values_list('slug', flat=True))
        self.assertEqual(len(slugs), 2)
        self.assertNotEqual(slugs[0], slugs[1])


# ─── Tests de asignación via API ─────────────────────────────────────────────

class AsignarEventoTests(TestCase):

    def setUp(self):
        self.dueno = _crear_usuario('dueno3', 'dueno')
        self.boliche = _crear_boliche(self.dueno)
        self.rrpp = _crear_rrpp(self.boliche, username='rrpp3')
        self.evento = _crear_evento(self.boliche)
        self.client = _auth_client(self.dueno)

    def test_asignar_evento_genera_2_links_en_respuesta(self):
        resp = self.client.post(
            f'/api/rrpp/{self.rrpp.pk}/asignar-evento/',
            {'evento_id': self.evento.pk},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(resp.data['links']), 2)
        tipos = {l['tipo'] for l in resp.data['links']}
        self.assertEqual(tipos, {'lista', 'venta_web'})

    def test_asignar_evento_links_tienen_slugs_distintos(self):
        resp = self.client.post(
            f'/api/rrpp/{self.rrpp.pk}/asignar-evento/',
            {'evento_id': self.evento.pk},
            format='json',
        )
        slugs = [l['slug'] for l in resp.data['links']]
        self.assertNotEqual(slugs[0], slugs[1])

    def test_asignar_evento_ajeno_al_boliche_devuelve_400(self):
        otro_dueno = _crear_usuario('otro3', 'dueno')
        otro_boliche = Boliche.objects.create(
            nombre='Otro', direccion='X', dueno=otro_dueno,
        )
        evento_ajeno = _crear_evento(otro_boliche, nombre='Ajeno')
        resp = self.client.post(
            f'/api/rrpp/{self.rrpp.pk}/asignar-evento/',
            {'evento_id': evento_ajeno.pk},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_asignar_evento_duplicado_devuelve_409(self):
        self.client.post(
            f'/api/rrpp/{self.rrpp.pk}/asignar-evento/',
            {'evento_id': self.evento.pk},
            format='json',
        )
        resp = self.client.post(
            f'/api/rrpp/{self.rrpp.pk}/asignar-evento/',
            {'evento_id': self.evento.pk},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_asignar_sin_auth_devuelve_401(self):
        client = APIClient()
        resp = client.post(
            f'/api/rrpp/{self.rrpp.pk}/asignar-evento/',
            {'evento_id': self.evento.pk},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ─── Tests del panel RRPP ────────────────────────────────────────────────────

class MiPanelTests(TestCase):

    def setUp(self):
        self.dueno = _crear_usuario('dueno4', 'dueno')
        self.boliche = _crear_boliche(self.dueno)
        self.rrpp = _crear_rrpp(self.boliche, username='rrpp4')
        self.evento = _crear_evento(self.boliche)
        AsignacionRRPP.objects.create(rrpp=self.rrpp, evento=self.evento)
        self.client = _auth_client(self.rrpp.usuario)

    def test_mi_panel_devuelve_asignaciones_propias(self):
        resp = self.client.get('/api/rrpp/mi-panel/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['evento_nombre'], 'Noche Techno')
        self.assertIn('links', resp.data[0])
        self.assertIn('estadisticas', resp.data[0])

    def test_mi_panel_no_muestra_asignaciones_de_otro_rrpp(self):
        otro_rrpp = _crear_rrpp(self.boliche, username='rrpp_otro')
        otro_evento = _crear_evento(self.boliche, nombre='Otra Noche')
        AsignacionRRPP.objects.create(rrpp=otro_rrpp, evento=otro_evento)

        resp = self.client.get('/api/rrpp/mi-panel/')
        nombres = [a['evento_nombre'] for a in resp.data]
        self.assertNotIn('Otra Noche', nombres)

    def test_mi_panel_sin_auth_devuelve_401(self):
        client = APIClient()
        resp = client.get('/api/rrpp/mi-panel/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_mi_panel_rol_incorrecto_devuelve_403(self):
        client = _auth_client(self.dueno)
        resp = client.get('/api/rrpp/mi-panel/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
