import logging

from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import CreateAPIView, ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cuentas.permissions import IsDueno

from .models import Evento
from .serializers import EventoDetailSerializer, EventoListSerializer
from .utils import calcular_precio_publicado

logger = logging.getLogger(__name__)


# ─── Listado público ─────────────────────────────────────────────────────────

class EventoListView(ListAPIView):
    """GET /api/eventos/ — Cartelera pública."""

    permission_classes = [AllowAny]
    serializer_class = EventoListSerializer

    def get_queryset(self):
        qs = Evento.objects.select_related('boliche').all()
        estado = self.request.query_params.get('estado')
        if estado:
            qs = qs.filter(estado=estado)
        return qs


# ─── Detalle + PATCH ─────────────────────────────────────────────────────────

class EventoDetailView(RetrieveAPIView):
    """
    GET /api/eventos/:id/ — Detalle público.
    PATCH /api/eventos/:id/ — Editar (IsDueno, solo su boliche).
    DELETE bloqueado.
    """

    permission_classes = [AllowAny]
    serializer_class = EventoDetailSerializer
    queryset = Evento.objects.select_related('boliche').all()

    def patch(self, request, *args, **kwargs):
        # Verificar auth
        if not request.user.is_authenticated or request.user.rol != 'dueno':
            return Response(status=status.HTTP_403_FORBIDDEN)

        evento = self.get_object()

        if evento.estado == 'cancelado':
            return Response(
                {'error': 'No se puede editar un evento cancelado'},
                status=status.HTTP_405_METHOD_NOT_ALLOWED,
            )

        if evento.boliche.dueno != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = EventoDetailSerializer(evento, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


# ─── Crear evento ────────────────────────────────────────────────────────────

class EventoCreateView(CreateAPIView):
    """POST /api/eventos/crear/ — Crear evento (IsDueno)."""

    permission_classes = [IsDueno]
    serializer_class = EventoDetailSerializer

    def perform_create(self, serializer):
        boliche = serializer.validated_data.get('boliche')
        if boliche.dueno != self.request.user:
            raise PermissionDenied('No podés crear eventos en un boliche que no es tuyo.')
        serializer.save()


# ─── Cancelar evento ─────────────────────────────────────────────────────────

def _intentar_reembolso(evento_id):
    """Intenta llamar a reembolsar_evento de apps.pagos. Si no existe, loguea y devuelve 0."""
    try:
        from apps.pagos.services import reembolsar_evento
        return reembolsar_evento(evento_id)
    except ImportError:
        logger.warning(
            "apps.pagos no disponible. Reembolsos no procesados para evento %s", evento_id
        )
        return 0


class EventoCancelarView(APIView):
    """POST /api/eventos/:id/cancelar/ — Cancelar evento (IsDueno)."""

    permission_classes = [IsDueno]

    def post(self, request, pk):
        try:
            evento = Evento.objects.select_related('boliche').get(pk=pk)
        except Evento.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if evento.estado == 'cancelado':
            return Response(
                {'error': 'El evento ya está cancelado'},
                status=status.HTTP_409_CONFLICT,
            )

        if evento.boliche.dueno != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)

        motivo = request.data.get('motivo', '').strip()
        if not motivo:
            return Response(
                {'error': 'El campo motivo es obligatorio'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        evento.estado = 'cancelado'
        evento.motivo_cancelacion = motivo
        evento.save(update_fields=['estado', 'motivo_cancelacion', 'updated_at'])

        reembolsos = _intentar_reembolso(evento.id)

        return Response({
            'id': evento.id,
            'estado': evento.estado,
            'motivo_cancelacion': evento.motivo_cancelacion,
            'reembolsos_iniciados': reembolsos,
        })


# ─── Calculadora de precios ──────────────────────────────────────────────────

class CalcularPrecioView(APIView):
    """GET /api/precios/calcular/?precio_base=X — Calcula desglose público."""

    permission_classes = [AllowAny]

    def get(self, request):
        precio_base = request.query_params.get('precio_base')
        if precio_base is None:
            return Response(
                {'error': 'El parámetro precio_base es obligatorio'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            resultado = calcular_precio_publicado(precio_base)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(resultado)
