"""
Vistas de la app pagos: preferencia MP, webhook, wallet y dashboards.
"""
import hashlib
import hmac
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cuentas.permissions import IsDueno, IsSuperAdmin
from apps.cuentas.throttles import PreferenciaRateThrottle, WebhookRateThrottle
from apps.eventos.models import Evento
from apps.puerta.models import Asistente

from . import mp_client
from .mp_client import MPError

logger = logging.getLogger(__name__)


# ─── Preferencia de pago ─────────────────────────────────────────────────────

class PreferenciaView(APIView):
    """POST /api/pagos/preferencia/ — Crea preferencia en MP y devuelve init_point."""

    permission_classes = [AllowAny]
    throttle_classes = [PreferenciaRateThrottle]

    def post(self, request):
        evento_id = request.data.get('evento_id')
        nombre = request.data.get('nombre', '').strip()
        apellido = request.data.get('apellido', '').strip()
        dni = request.data.get('dni', '').strip()
        email = request.data.get('email', '').strip()

        if not all([evento_id, nombre, apellido, dni, email]):
            return Response(
                {'error': 'Los campos evento_id, nombre, apellido, dni y email son obligatorios.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            evento = Evento.objects.select_related('boliche').get(pk=evento_id)
        except Evento.DoesNotExist:
            return Response(
                {'error': 'El evento no existe.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if evento.estado == 'cancelado':
            return Response(
                {'error': 'El evento no está disponible.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if Asistente.objects.filter(evento=evento, dni=dni).exists():
            return Response(
                {'error': 'Ya tenés una entrada para este evento.'},
                status=status.HTTP_409_CONFLICT,
            )

        comprador = {'nombre': nombre, 'apellido': apellido, 'email': email, 'dni': dni}

        try:
            result = mp_client.crear_preferencia(evento, comprador)
        except MPError as e:
            logger.error("Error MP al crear preferencia: %s", e)
            return Response(
                {'error': 'Error al conectar con Mercado Pago.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        from apps.eventos.utils import calcular_precio_publicado
        desglose = calcular_precio_publicado(evento.precio_base)

        return Response({
            'init_point': result['init_point'],
            'preference_id': result['preference_id'],
            'precio_publicado': desglose['precio_publicado'],
            'desglose': desglose,
        })


# ─── Webhook de Mercado Pago ─────────────────────────────────────────────────

class WebhookView(APIView):
    """POST /api/pagos/webhook/ — Recibe notificaciones de MP."""

    permission_classes = [AllowAny]
    throttle_classes = [WebhookRateThrottle]

    def post(self, request):
        # Validar firma de MP (si está configurado el secret)
        if settings.MP_WEBHOOK_SECRET and not self._validar_firma(request):
            logger.warning("Webhook con firma inválida desde IP %s", request.META.get('REMOTE_ADDR'))
            return Response({'ok': True})  # Responder 200 igual, pero no procesar

        # Siempre responder 200 para que MP no reintente
        try:
            data = request.data
            topic = data.get('type') or request.query_params.get('topic', '')

            if topic != 'payment':
                return Response({'ok': True})

            payment_id = str(
                data.get('data', {}).get('id')
                or request.query_params.get('id', '')
            )
            if not payment_id:
                return Response({'ok': True})

            # Idempotencia
            if Asistente.objects.filter(mp_payment_id=payment_id).exists():
                return Response({'ok': True})

            # Obtener datos del pago
            pago = mp_client.obtener_pago(payment_id)
            if pago.get('status') != 'approved':
                return Response({'ok': True})

            # Extraer datos del comprador
            metadata = pago.get('metadata', {})
            evento_id = metadata.get('evento_id')
            dni = metadata.get('dni') or pago.get('payer', {}).get('email', '')
            nombre = metadata.get('nombre') or pago.get('payer', {}).get('first_name', '')
            apellido = metadata.get('apellido') or pago.get('payer', {}).get('last_name', '')

            if not evento_id:
                logger.warning("Webhook sin evento_id en metadata, payment_id=%s", payment_id)
                return Response({'ok': True})

            evento = Evento.objects.get(pk=evento_id)

            # Calcular fee real
            fee_details = pago.get('fee_details', [])
            fee_real = fee_details[0].get('amount', 0) if fee_details else 0

            # Crear asistente
            asistente = Asistente.objects.create(
                evento=evento,
                nombre=nombre,
                apellido=apellido,
                dni=dni,
                tipo_ingreso='web_anticipada',
                estado='aprobado_guardia',
                metodo_pago='ya_pago_web',
                monto_pagado=pago.get('transaction_amount'),
                mp_payment_id=payment_id,
                mp_fee_norware=fee_real,
            )

            # Enviar mail
            _enviar_mail_confirmacion(asistente, pago.get('payer', {}).get('email'))

        except Exception as e:
            logger.error("Error procesando webhook: %s", e)

        return Response({'ok': True})

    def _validar_firma(self, request):
        """Valida la firma HMAC de Mercado Pago en el header x-signature."""
        x_signature = request.headers.get('x-signature', '')
        x_request_id = request.headers.get('x-request-id', '')

        if not x_signature:
            return False

        # Parsear ts y v1 del header
        parts = {}
        for segment in x_signature.split(','):
            if '=' in segment:
                key, value = segment.strip().split('=', 1)
                parts[key] = value

        ts = parts.get('ts', '')
        v1 = parts.get('v1', '')
        if not ts or not v1:
            return False

        # Construir manifest según docs de MP
        data_id = request.query_params.get('data.id', '')
        manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"

        # Calcular HMAC-SHA256
        expected = hmac.new(
            settings.MP_WEBHOOK_SECRET.encode(),
            manifest.encode(),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(v1, expected)


def _enviar_mail_confirmacion(asistente, email_destinatario):
    """Envía mail con link al wallet del comprador."""
    if not email_destinatario:
        return

    wallet_url = f"{settings.FRONTEND_URL}/wallet/{asistente.wallet_token}"
    try:
        send_mail(
            subject=f"Tu entrada para {asistente.evento.nombre}",
            message=(
                f"Hola {asistente.nombre},\n\n"
                f"Tu entrada está confirmada.\n"
                f"Accedé a tu ticket acá: {wallet_url}\n\n"
                f"Presentá el QR en la puerta del evento."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email_destinatario],
            fail_silently=True,
        )
    except Exception as e:
        logger.error("Error enviando mail confirmación: %s", e)


# ─── Wallet público ──────────────────────────────────────────────────────────

class WalletView(APIView):
    """GET /api/wallet/:token/ — Ticket público del comprador."""

    permission_classes = [AllowAny]

    def get(self, request, token):
        asistente = get_object_or_404(
            Asistente.objects.select_related('evento__boliche'),
            wallet_token=token,
        )
        evento = asistente.evento

        return Response({
            'token': str(asistente.wallet_token),
            'nombre': asistente.nombre,
            'apellido': asistente.apellido,
            'dni': asistente.dni,
            'estado': asistente.estado,
            'tipo_ingreso': asistente.tipo_ingreso,
            'evento': {
                'id': evento.id,
                'nombre': evento.nombre,
                'fecha': evento.fecha,
                'boliche': evento.boliche.nombre,
                'color_pulsera': evento.color_pulsera,
            },
            'qr_code': str(asistente.wallet_token),
            'evento_cancelado': evento.estado == 'cancelado',
            'motivo_cancelacion': evento.motivo_cancelacion,
        })


# ─── Dashboard Recaudación ───────────────────────────────────────────────────

class RecaudacionView(APIView):
    """GET /api/dashboard/recaudacion/:evento_id/ — Desglose por método de pago."""

    permission_classes = [IsDueno]

    def get(self, request, evento_id):
        evento = get_object_or_404(Evento.objects.select_related('organizador'), pk=evento_id)

        if evento.organizador != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)

        qs = Asistente.objects.filter(evento=evento, estado='ingresado_final')

        web = qs.filter(tipo_ingreso='web_anticipada').aggregate(
            monto=Sum('monto_pagado'), cantidad=Count('id'),
            comision_norware=Sum('mp_fee_norware'),
        )
        efectivo = qs.filter(metodo_pago='efectivo').aggregate(
            monto=Sum('monto_pagado'), cantidad=Count('id'),
        )
        transferencia = qs.filter(metodo_pago='transferencia').aggregate(
            monto=Sum('monto_pagado'), cantidad=Count('id'),
        )

        total = (web['monto'] or 0) + (efectivo['monto'] or 0) + (transferencia['monto'] or 0)

        return Response({
            'evento_id': evento_id,
            'web': {
                'cantidad': web['cantidad'] or 0,
                'monto_bruto': float(web['monto'] or 0),
                'comision_norware': float(web['comision_norware'] or 0),
            },
            'efectivo': {
                'cantidad': efectivo['cantidad'] or 0,
                'monto': float(efectivo['monto'] or 0),
            },
            'transferencia': {
                'cantidad': transferencia['cantidad'] or 0,
                'monto': float(transferencia['monto'] or 0),
            },
            'total_recaudado': float(total),
            'comision_norware_web': float(web['comision_norware'] or 0),
        })


# ─── Dashboard Ranking RRPP ──────────────────────────────────────────────────

class RankingRRPPView(APIView):
    """GET /api/dashboard/ranking-rrpp/:evento_id/ — Ranking RRPP del evento."""

    permission_classes = [IsDueno]

    def get(self, request, evento_id):
        evento = get_object_or_404(Evento.objects.select_related('organizador'), pk=evento_id)

        if evento.organizador != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)

        from apps.rrpp.models import AsignacionRRPP

        asignaciones = AsignacionRRPP.objects.filter(
            evento=evento,
        ).select_related('rrpp__usuario')

        ranking = []
        for asig in asignaciones:
            qs = Asistente.objects.filter(link_rrpp__asignacion=asig)
            anotados = qs.count()
            ingresados = qs.filter(estado='ingresado_final').count()
            rebotados = qs.filter(estado='rebotado_guardia').count()
            recaudado = float(
                qs.filter(estado='ingresado_final').aggregate(t=Sum('monto_pagado'))['t'] or 0
            )

            rrpp_obj = asig.rrpp
            if asig.tipo_comision == 'fijo':
                comision = float(asig.valor_comision) * ingresados
            else:
                comision = recaudado * float(asig.valor_comision) / 100

            ranking.append({
                'rrpp_id': rrpp_obj.id,
                'nombre': rrpp_obj.usuario.get_full_name() or rrpp_obj.usuario.username,
                'tipo_comision': asig.tipo_comision,
                'valor_comision': float(asig.valor_comision),
                'anotados': anotados,
                'ingresados': ingresados,
                'rebotados': rebotados,
                'tasa_conversion': round(ingresados / anotados * 100, 2) if anotados else 0,
                'recaudado_total': recaudado,
                'comision_a_pagar': round(comision, 2),
            })

        return Response(ranking)


# ─── Métricas Superadmin ─────────────────────────────────────────────────────

class MetricasAdminView(APIView):
    """GET /api/admin/metricas/ — Métricas globales de Norware."""

    permission_classes = [IsSuperAdmin]

    def get(self, request):
        eventos = Evento.objects.select_related('boliche').all()

        por_evento = []
        total_comision_norware = 0
        total_entradas_web = 0

        for evento in eventos:
            qs_web = Asistente.objects.filter(
                evento=evento, tipo_ingreso='web_anticipada',
            )
            entradas_web = qs_web.count()
            comision = float(qs_web.aggregate(c=Sum('mp_fee_norware'))['c'] or 0)
            recaudado_web = float(qs_web.aggregate(r=Sum('monto_pagado'))['r'] or 0)

            total_comision_norware += comision
            total_entradas_web += entradas_web

            por_evento.append({
                'evento_id': evento.id,
                'evento_nombre': evento.nombre,
                'boliche': evento.boliche.nombre,
                'fecha': evento.fecha,
                'estado': evento.estado,
                'entradas_web': entradas_web,
                'comision_norware': round(comision, 2),
                'recaudado_total_web': round(recaudado_web, 2),
            })

        return Response({
            'totales': {
                'entradas_web_total': total_entradas_web,
                'comision_norware_total': round(total_comision_norware, 2),
                'eventos_activos': eventos.filter(estado='activo').count(),
                'eventos_cancelados': eventos.filter(estado='cancelado').count(),
            },
            'por_evento': por_evento,
        })
