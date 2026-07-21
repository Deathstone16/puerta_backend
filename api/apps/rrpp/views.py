from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.boliches.models import Boliche
from apps.cuentas.permissions import IsDueno, IsRRPP
from apps.eventos.models import Evento

from .models import AsignacionRRPP, LinkRRPP, RRPP
from .serializers import (
    AsignacionConEstadisticasSerializer,
    LinkRRPPSerializer,
    RRPPCreateSerializer,
    RRPPSerializer,
)


class RRPPListCreateView(APIView):
    """
    GET /api/rrpp/ — Lista RRPP del boliche del dueño.
    POST /api/rrpp/ — Alta de RRPP (transacción atómica).
    """

    permission_classes = [IsDueno]

    def _get_boliche(self, user):
        try:
            return Boliche.objects.get(dueno=user)
        except Boliche.DoesNotExist:
            return None

    def get(self, request):
        boliche = self._get_boliche(request.user)
        if not boliche:
            return Response([], status=status.HTTP_200_OK)
        rrpps = RRPP.objects.filter(boliche=boliche).select_related('usuario').prefetch_related(
            'asignaciones__evento', 'asignaciones__links',
        )
        return Response(RRPPSerializer(rrpps, many=True).data)

    def post(self, request):
        boliche = self._get_boliche(request.user)
        if not boliche:
            return Response(
                {'error': 'Primero debés crear un boliche.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = RRPPCreateSerializer(data=request.data, context={'boliche': boliche})
        if serializer.is_valid():
            rrpp = serializer.save()
            return Response(RRPPSerializer(rrpp).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AsignarEventoView(APIView):
    """POST /api/rrpp/:id/asignar-evento/ — Asigna RRPP a evento, genera 2 links."""

    permission_classes = [IsDueno]

    def post(self, request, pk):
        rrpp = get_object_or_404(RRPP, pk=pk)

        # Verificar que el RRPP pertenece al boliche del dueño
        boliche = rrpp.boliche
        if boliche.dueno != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)

        evento_id = request.data.get('evento_id')
        if not evento_id:
            return Response(
                {'error': 'El campo evento_id es obligatorio.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            evento = Evento.objects.get(pk=evento_id)
        except Evento.DoesNotExist:
            return Response(
                {'error': 'El evento no existe.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if evento.boliche != boliche:
            return Response(
                {'error': 'El evento no pertenece a tu boliche.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if AsignacionRRPP.objects.filter(rrpp=rrpp, evento=evento).exists():
            return Response(
                {'error': 'El RRPP ya está asignado a este evento.'},
                status=status.HTTP_409_CONFLICT,
            )

        asignacion = AsignacionRRPP.objects.create(rrpp=rrpp, evento=evento)
        # La signal post_save genera los 2 links automáticamente
        links = asignacion.links.all()

        return Response({
            'asignacion_id': asignacion.id,
            'rrpp_nombre': str(rrpp),
            'evento_nombre': evento.nombre,
            'links': LinkRRPPSerializer(links, many=True).data,
        }, status=status.HTTP_201_CREATED)


class MiPanelView(APIView):
    """GET /api/rrpp/mi-panel/ — Panel del RRPP autenticado."""

    permission_classes = [IsRRPP]

    def get(self, request):
        rrpp = get_object_or_404(RRPP, usuario=request.user)
        asignaciones = (
            AsignacionRRPP.objects
            .filter(rrpp=rrpp, activa=True)
            .select_related('evento')
            .prefetch_related('links')
        )
        return Response(AsignacionConEstadisticasSerializer(asignaciones, many=True).data)


class AnotarInvitadoView(APIView):
    """POST /api/rrpp/anotar-invitado/ — Carga manual de invitado."""

    permission_classes = [IsRRPP]

    def post(self, request):
        slug_lista = request.data.get('slug_lista')
        nombre = request.data.get('nombre', '').strip()
        apellido = request.data.get('apellido', '').strip()
        dni = request.data.get('dni', '').strip()

        if not all([slug_lista, nombre, apellido, dni]):
            return Response(
                {'error': 'Los campos slug_lista, nombre, apellido y dni son obligatorios.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            link = LinkRRPP.objects.select_related(
                'asignacion__rrpp__usuario', 'asignacion__evento',
            ).get(slug=slug_lista, tipo='lista')
        except LinkRRPP.DoesNotExist:
            return Response(
                {'error': 'Link no encontrado.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Verificar que pertenece al RRPP autenticado
        if link.asignacion.rrpp.usuario != request.user:
            return Response(
                {'error': 'Este link no te pertenece.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not link.activo:
            return Response(
                {'error': 'Este link está inactivo.'},
                status=status.HTTP_410_GONE,
            )

        evento = link.asignacion.evento

        # Verificar DNI duplicado
        try:
            from apps.puerta.models import Asistente
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
                tipo_ingreso='lista_rrpp',
                estado='pendiente',
            )
            return Response({
                'id': asistente.id,
                'nombre': f"{asistente.nombre} {asistente.apellido}",
                'dni': asistente.dni,
                'estado': asistente.estado,
            }, status=status.HTTP_201_CREATED)
        except ImportError:
            return Response(
                {'error': 'La app puerta no está disponible aún.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
