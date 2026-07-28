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


def _resolver_link_slug(link_slug, evento):
    """Devuelve el slug si corresponde a un LinkRRPP activo del evento, si no None.

    El slug es un UUID: si llega mal formado se ignora en vez de romper el checkout.
    """
    if not link_slug:
        return None
    from django.core.exceptions import ValidationError as DjangoValidationError
    from apps.rrpp.models import LinkRRPP
    try:
        existe = LinkRRPP.objects.filter(
            slug=link_slug, activo=True, asignacion__evento=evento, asignacion__activa=True,
        ).exists()
    except (DjangoValidationError, ValueError, TypeError):
        existe = False
    if not existe:
        logger.info("link_slug %r no válido para evento %s, se ignora", link_slug, evento.id)
        return None
    return str(link_slug)


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
        link_slug = (request.data.get('link_slug') or '').strip()

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

        # Atribución RRPP: el slug tiene que ser un link de venta/lista activo DEL MISMO evento.
        # Si no valida, la compra sigue como venta web directa (sin atribución) en vez de fallar.
        link_slug_valido = _resolver_link_slug(link_slug, evento)

        comprador = {'nombre': nombre, 'apellido': apellido, 'email': email, 'dni': dni}

        try:
            result = mp_client.crear_preferencia(evento, comprador, link_slug=link_slug_valido)
        except MPError as e:
            logger.error("Error MP al crear preferencia: %s", e)
            # El mensaje de MPError es informativo y seguro de mostrar (ej. "el
            # organizador no conectó Mercado Pago" / "el evento no tiene boliche").
            return Response(
                {'error': str(e) or 'Error al conectar con Mercado Pago.'},
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

            # Extract buyer data
            metadata = pago.get('metadata', {})
            evento_id = metadata.get('evento_id')
            dni = metadata.get('dni')
            nombre = metadata.get('nombre')
            apellido = metadata.get('apellido')

            if not evento_id:
                logger.warning("Webhook sin evento_id en metadata, payment_id=%s", payment_id)
                return Response({'ok': True})

            if not all([dni, nombre, apellido]):
                logger.error("Webhook metadata incompleta, payment_id=%s metadata=%s", payment_id, metadata)
                return Response({'ok': True})

            evento = Evento.objects.get(pk=evento_id)

            # El marketplace_fee de Norware es típicamente el último fee en la lista
            fee_details = pago.get('fee_details', [])
            fee_real = fee_details[-1].get('amount', 0) if fee_details else 0

            # Atribución RRPP: si la compra vino de un link, la venta se le acredita.
            link_rrpp = None
            link_slug = metadata.get('link_slug')
            if link_slug:
                from apps.rrpp.models import LinkRRPP
                try:
                    link_rrpp = LinkRRPP.objects.filter(
                        slug=link_slug, asignacion__evento=evento,
                    ).first()
                except Exception:
                    link_rrpp = None

            # Crear asistente
            asistente = Asistente.objects.create(
                evento=evento,
                link_rrpp=link_rrpp,
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
        expected = hmac.HMAC(
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
            'codigo': f"N{asistente.id:04d}-{str(asistente.wallet_token)[:8].upper()}",
            'nombre': asistente.nombre,
            'apellido': asistente.apellido,
            'dni': asistente.dni,
            'estado': asistente.estado,
            'tipo_ingreso': asistente.tipo_ingreso,
            'evento': {
                'id': evento.id,
                'nombre': evento.nombre,
                'fecha': evento.fecha,
                'fecha_corta': evento.fecha.strftime('%a %d %b').upper() if evento.fecha else None,
                'horario': evento.fecha.strftime('%H:%M') if evento.fecha else None,
                'boliche': evento.boliche.nombre if evento.boliche else None,
                'club': evento.boliche.nombre if evento.boliche else None,
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

        return Response(_build_recaudacion(evento))


class RecaudacionCajeraView(APIView):
    """GET /api/cajera/cierre/ — Cierre de caja para la cajera (su evento asignado)."""

    from rest_framework.permissions import IsAuthenticated
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.cuentas.models import AsignacionStaff

        if request.user.rol != 'cajera':
            return Response(status=status.HTTP_403_FORBIDDEN)

        # Find the cajera's active assignment
        asignacion = AsignacionStaff.objects.filter(
            usuario=request.user, activa=True, rol='cajera',
        ).select_related('evento').first()

        if not asignacion:
            return Response(
                {'error': 'No tenés un evento asignado activo.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(_build_recaudacion(asignacion.evento))


def _build_recaudacion(evento):
    """Shared helper: builds recaudación response for a given evento."""
    qs = Asistente.objects.filter(evento=evento, estado='ingresado_final')
    qs_web_pendiente = Asistente.objects.filter(
        evento=evento, tipo_ingreso='web_anticipada', estado__in=['pendiente', 'aprobado_guardia']
    )

    web = qs.filter(tipo_ingreso='web_anticipada').aggregate(
        monto=Sum('monto_pagado'), cantidad=Count('id'),
        comision_norware=Sum('mp_fee_norware'),
    )
    web_pendiente = qs_web_pendiente.aggregate(
        monto=Sum('monto_pagado'), cantidad=Count('id'),
    )
    efectivo = qs.filter(metodo_pago='efectivo').aggregate(
        monto=Sum('monto_pagado'), cantidad=Count('id'),
    )
    transferencia = qs.filter(metodo_pago='transferencia').aggregate(
        monto=Sum('monto_pagado'), cantidad=Count('id'),
    )

    total = (web['monto'] or 0) + (efectivo['monto'] or 0) + (transferencia['monto'] or 0)

    return {
        'evento_id': evento.id,
        'evento_nombre': evento.nombre,
        'web': {
            'cantidad': web['cantidad'] or 0,
            'monto_bruto': float(web['monto'] or 0),
            'comision_norware': float(web['comision_norware'] or 0),
            'pendiente_ingreso': web_pendiente['cantidad'] or 0,
            'pendiente_monto': float(web_pendiente['monto'] or 0),
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
    }


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
            evento=evento, activa=True,
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
            valor_comision = float(asig.valor_comision or 0)
            if asig.tipo_comision == 'fijo':
                comision = valor_comision * ingresados
            else:
                comision = recaudado * valor_comision / 100

            ranking.append({
                'rrpp_id': rrpp_obj.id,
                'nombre': rrpp_obj.usuario.get_full_name() or rrpp_obj.usuario.username,
                'tipo_comision': asig.tipo_comision,
                'valor_comision': valor_comision,
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
                'boliche': evento.boliche.nombre if evento.boliche else 'Sin boliche',
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
