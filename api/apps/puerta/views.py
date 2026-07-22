from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cuentas.permissions import IsCajera, IsDueno, IsGuardia
from apps.eventos.models import Evento
from apps.rrpp.models import LinkRRPP

from .mixins import EventoActivoMixin
from .models import Asistente


# ─── Endpoints públicos de lista ─────────────────────────────────────────────

class ListaInfoView(APIView):
    """GET /api/lista/:slug/ — Info pública del link de lista."""

    permission_classes = [AllowAny]

    def get(self, request, slug):
        try:
            link = LinkRRPP.objects.select_related(
                'asignacion__evento__boliche', 'asignacion__rrpp__usuario',
            ).get(slug=slug, tipo='lista')
        except LinkRRPP.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if not link.activo:
            return Response({'error': 'Este link está inactivo.'}, status=status.HTTP_410_GONE)

        evento = link.asignacion.evento
        anotados = Asistente.objects.filter(link_rrpp=link).count()
        rrpp_user = link.asignacion.rrpp.usuario

        return Response({
            'evento': {
                'id': evento.id,
                'nombre': evento.nombre,
                'fecha': evento.fecha,
                'boliche': evento.boliche.nombre,
                'color_pulsera': evento.color_pulsera,
                'habilitar_lista': evento.habilitar_lista,
            },
            'rrpp_nombre': rrpp_user.get_full_name() or rrpp_user.username,
            'link_activo': True,
            'anotados': anotados,
        })


class ListaAnotarView(EventoActivoMixin, APIView):
    """POST /api/lista/:slug/anotar/ — Anotarse a la lista (público)."""

    permission_classes = [AllowAny]

    def post(self, request, slug):
        try:
            link = LinkRRPP.objects.select_related(
                'asignacion__evento',
            ).get(slug=slug, tipo='lista')
        except LinkRRPP.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if not link.activo:
            return Response({'error': 'Este link está inactivo.'}, status=status.HTTP_410_GONE)

        evento = link.asignacion.evento
        bloqueo = self.verificar_evento_activo(evento)
        if bloqueo:
            return bloqueo

        nombre = request.data.get('nombre', '').strip()
        apellido = request.data.get('apellido', '').strip()
        dni = request.data.get('dni', '').strip()
        instagram = request.data.get('instagram', '').strip()

        if not all([nombre, apellido, dni]):
            return Response(
                {'error': 'Los campos nombre, apellido y dni son obligatorios.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if Asistente.objects.filter(evento=evento, dni=dni).exists():
            return Response(
                {'error': 'Este DNI ya está registrado en el evento.'},
                status=status.HTTP_409_CONFLICT,
            )

        asistente = Asistente.objects.create(
            evento=evento,
            link_rrpp=link,
            nombre=nombre,
            apellido=apellido,
            dni=dni,
            instagram=instagram,
            tipo_ingreso='lista_rrpp',
            estado='pendiente',
        )

        return Response({
            'id': asistente.id,
            'nombre': f"{asistente.nombre} {asistente.apellido}",
            'dni': asistente.dni,
            'instagram': asistente.instagram,
            'estado': asistente.estado,
            'evento': evento.nombre,
            'rrpp_nombre': link.asignacion.rrpp.usuario.get_full_name(),
            'mensaje': 'Te anotamos. El RRPP va a validar tu solicitud.',
        }, status=status.HTTP_201_CREATED)


# ─── Endpoints de Guardia ────────────────────────────────────────────────────

class GuardiaEscanearView(EventoActivoMixin, APIView):
    """POST /api/puerta/guardia/escanear/ — Buscar asistente por QR o DNI."""

    permission_classes = [IsGuardia]

    def post(self, request):
        qr_code = request.data.get('qr_code')
        dni = request.data.get('dni')
        evento_id = request.data.get('evento_id')

        if qr_code:
            try:
                asistente = Asistente.objects.select_related('evento', 'link_rrpp').get(
                    wallet_token=qr_code,
                )
            except (Asistente.DoesNotExist, ValueError):
                return Response(
                    {'error': 'No encontrado en la lista de este evento.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
        elif dni and evento_id:
            try:
                asistente = Asistente.objects.select_related('evento', 'link_rrpp').get(
                    dni=dni, evento_id=evento_id,
                )
            except Asistente.DoesNotExist:
                return Response(
                    {'error': 'No encontrado en la lista de este evento.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            return Response(
                {'error': 'Enviar qr_code o (dni + evento_id).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        bloqueo = self.verificar_evento_activo(asistente.evento)
        if bloqueo:
            return bloqueo

        rrpp_nombre = None
        if asistente.link_rrpp:
            rrpp_user = asistente.link_rrpp.asignacion.rrpp.usuario
            rrpp_nombre = rrpp_user.get_full_name() or rrpp_user.username

        return Response({
            'id': asistente.id,
            'nombre': f"{asistente.nombre} {asistente.apellido}",
            'dni': asistente.dni,
            'tipo_ingreso': asistente.tipo_ingreso,
            'estado': asistente.estado,
            'rrpp_nombre': rrpp_nombre,
        })


class GuardiaAprobarView(EventoActivoMixin, APIView):
    """POST /api/puerta/guardia/aprobar/:id/ — Aprobar asistente."""

    permission_classes = [IsGuardia]

    def post(self, request, pk):
        asistente = get_object_or_404(Asistente.objects.select_related('evento'), pk=pk)
        bloqueo = self.verificar_evento_activo(asistente.evento)
        if bloqueo:
            return bloqueo

        if asistente.estado != 'pendiente':
            return Response(
                {'error': 'El asistente no está en estado pendiente.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        asistente.estado = 'aprobado_guardia'
        asistente.aprobado_at = timezone.now()
        asistente.save(update_fields=['estado', 'aprobado_at'])

        return Response({
            'id': asistente.id,
            'estado': 'aprobado_guardia',
            'aprobado_at': asistente.aprobado_at,
            'mensaje': 'Aprobado. Pasa a caja.',
        })


class GuardiaRebotarView(EventoActivoMixin, APIView):
    """POST /api/puerta/guardia/rebotar/:id/ — Rebotar asistente (terminal)."""

    permission_classes = [IsGuardia]

    def post(self, request, pk):
        asistente = get_object_or_404(Asistente.objects.select_related('evento'), pk=pk)
        bloqueo = self.verificar_evento_activo(asistente.evento)
        if bloqueo:
            return bloqueo

        if asistente.estado != 'pendiente':
            return Response(
                {'error': 'El asistente no está en estado pendiente.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        motivo = request.data.get('motivo', '').strip()
        if not motivo:
            return Response(
                {'error': 'El motivo es obligatorio.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        asistente.estado = 'rebotado_guardia'
        asistente.rebotado_at = timezone.now()
        asistente.motivo_rechazo = motivo
        asistente.save(update_fields=['estado', 'rebotado_at', 'motivo_rechazo'])

        return Response({
            'id': asistente.id,
            'estado': 'rebotado_guardia',
            'rebotado_at': asistente.rebotado_at,
            'motivo': motivo,
        })


# ─── Endpoints de Cajera ─────────────────────────────────────────────────────

def _validar_aprobado_guardia(asistente):
    """Helper: devuelve Response 409 si el asistente no fue aprobado por guardia."""
    if asistente.estado != 'aprobado_guardia':
        return Response(
            {'error': 'Falta validación del guardia.', 'estado_actual': asistente.estado},
            status=status.HTTP_409_CONFLICT,
        )
    return None


class CajeraEscanearWebView(EventoActivoMixin, APIView):
    """POST /api/puerta/cajera/escanear-web/:id/ — Ingreso web anticipada."""

    permission_classes = [IsCajera]

    def post(self, request, pk):
        asistente = get_object_or_404(Asistente.objects.select_related('evento'), pk=pk)
        bloqueo = self.verificar_evento_activo(asistente.evento)
        if bloqueo:
            return bloqueo

        if asistente.tipo_ingreso != 'web_anticipada':
            return Response(
                {'error': 'Este asistente no es de compra web.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        error = _validar_aprobado_guardia(asistente)
        if error:
            return error

        asistente.estado = 'ingresado_final'
        asistente.metodo_pago = 'ya_pago_web'
        asistente.ingresado_at = timezone.now()
        asistente.save(update_fields=['estado', 'metodo_pago', 'ingresado_at'])

        return Response({
            'id': asistente.id,
            'nombre': f"{asistente.nombre} {asistente.apellido}",
            'estado': 'ingresado_final',
            'metodo_pago': 'ya_pago_web',
            'ingresado_at': asistente.ingresado_at,
            'color_pulsera': asistente.evento.color_pulsera,
            'mensaje': f"Ingreso confirmado. Entregar pulsera {asistente.evento.color_pulsera}.",
        })


class CajeraCobrarListaView(EventoActivoMixin, APIView):
    """POST /api/puerta/cajera/cobrar-lista/:id/ — Cobrar a asistente de lista."""

    permission_classes = [IsCajera]

    def post(self, request, pk):
        asistente = get_object_or_404(Asistente.objects.select_related('evento'), pk=pk)
        bloqueo = self.verificar_evento_activo(asistente.evento)
        if bloqueo:
            return bloqueo

        error = _validar_aprobado_guardia(asistente)
        if error:
            return error

        metodo_pago = request.data.get('metodo_pago')
        monto_pagado = request.data.get('monto_pagado')

        if metodo_pago not in ('efectivo', 'transferencia'):
            return Response(
                {'error': 'metodo_pago debe ser "efectivo" o "transferencia".'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not monto_pagado:
            return Response(
                {'error': 'El campo monto_pagado es obligatorio.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        asistente.estado = 'ingresado_final'
        asistente.metodo_pago = metodo_pago
        asistente.monto_pagado = monto_pagado
        asistente.ingresado_at = timezone.now()
        asistente.save(update_fields=['estado', 'metodo_pago', 'monto_pagado', 'ingresado_at'])

        return Response({
            'id': asistente.id,
            'nombre': f"{asistente.nombre} {asistente.apellido}",
            'estado': 'ingresado_final',
            'metodo_pago': metodo_pago,
            'monto_pagado': float(asistente.monto_pagado),
            'ingresado_at': asistente.ingresado_at,
            'color_pulsera': asistente.evento.color_pulsera,
            'mensaje': f"Ingreso confirmado. Entregar pulsera {asistente.evento.color_pulsera}.",
        })


class CajeraVentaGeneralView(EventoActivoMixin, APIView):
    """POST /api/puerta/cajera/venta-general/ — Venta en puerta sin lista."""

    permission_classes = [IsCajera]

    def post(self, request):
        evento_id = request.data.get('evento_id')
        personas = request.data.get('personas', [])

        if not evento_id:
            return Response(
                {'error': 'El campo evento_id es obligatorio.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not personas:
            return Response(
                {'error': 'El campo personas es obligatorio y no puede estar vacío.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        evento = get_object_or_404(Evento, pk=evento_id)
        bloqueo = self.verificar_evento_activo(evento)
        if bloqueo:
            return bloqueo

        # Verificar DNIs duplicados dentro del request
        dnis_request = [p.get('dni', '').strip() for p in personas]
        if len(dnis_request) != len(set(dnis_request)):
            return Response(
                {'error': 'Hay DNIs duplicados en la lista enviada.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verificar DNIs existentes en el evento
        existentes = set(
            Asistente.objects.filter(evento=evento, dni__in=dnis_request)
            .values_list('dni', flat=True)
        )
        if existentes:
            return Response(
                {'error': 'DNIs ya registrados en el evento.', 'dnis': list(existentes)},
                status=status.HTTP_409_CONFLICT,
            )

        now = timezone.now()
        asistentes = []
        for p in personas:
            asistentes.append(Asistente(
                evento=evento,
                nombre=p.get('nombre', '').strip(),
                apellido=p.get('apellido', '').strip(),
                dni=p.get('dni', '').strip(),
                tipo_ingreso='venta_general',
                estado='ingresado_final',
                metodo_pago=p.get('metodo_pago', 'efectivo'),
                monto_pagado=p.get('monto_pagado'),
                ingresado_at=now,
            ))

        created = Asistente.objects.bulk_create(asistentes)

        return Response({
            'creados': len(created),
            'color_pulsera': evento.color_pulsera,
            'asistentes': [
                {'id': a.id, 'nombre': f"{a.nombre} {a.apellido}", 'dni': a.dni, 'estado': a.estado}
                for a in created
            ],
            'mensaje': f"Ingreso confirmado. Entregar pulsera {evento.color_pulsera}.",
        }, status=status.HTTP_201_CREATED)


class CajeraDeshacerView(APIView):
    """POST /api/puerta/cajera/deshacer/:id/ — Revertir ingreso (10 min)."""

    permission_classes = [IsCajera]

    def post(self, request, pk):
        asistente = get_object_or_404(Asistente.objects.select_related('evento'), pk=pk)

        if asistente.estado != 'ingresado_final':
            return Response(
                {'error': 'El asistente no está en estado ingresado_final.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        delta = timezone.now() - asistente.ingresado_at
        if delta > timedelta(minutes=10):
            return Response(
                {'error': 'No se puede deshacer: pasaron más de 10 minutos.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        asistente.estado = 'aprobado_guardia'
        asistente.ingresado_at = None
        asistente.metodo_pago = None
        asistente.monto_pagado = None
        asistente.save(update_fields=['estado', 'ingresado_at', 'metodo_pago', 'monto_pagado'])

        return Response({
            'id': asistente.id,
            'estado': 'aprobado_guardia',
            'mensaje': 'Ingreso revertido. El asistente vuelve a estar pendiente de cobro.',
        })


# ─── Dashboard — Aforo ───────────────────────────────────────────────────────

class AforoView(APIView):
    """GET /api/dashboard/aforo/:evento_id/ — Aforo en vivo."""

    permission_classes = [IsGuardia | IsCajera | IsDueno]

    def get(self, request, evento_id):
        evento = get_object_or_404(Evento, pk=evento_id)
        ingresados = Asistente.objects.filter(evento=evento, estado='ingresado_final').count()
        pendientes = Asistente.objects.filter(
            evento=evento, estado__in=['pendiente', 'aprobado_guardia'],
        ).count()
        porcentaje = round((ingresados / evento.aforo_max) * 100, 2) if evento.aforo_max else 0

        return Response({
            'evento_id': evento.id,
            'ingresados': ingresados,
            'aforo_max': evento.aforo_max,
            'porcentaje': porcentaje,
            'pendientes': pendientes,
        })
