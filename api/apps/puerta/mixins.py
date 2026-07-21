from rest_framework import status
from rest_framework.response import Response


class EventoActivoMixin:
    """
    Mixin para vistas de puerta. Verifica que el evento esté activo.
    Si el evento está cancelado → HTTP 423 LOCKED.
    """

    def verificar_evento_activo(self, evento):
        if evento.estado == 'cancelado':
            return Response(
                {
                    'error': 'SISTEMA BLOQUEADO - EVENTO CANCELADO',
                    'motivo': evento.motivo_cancelacion or '',
                },
                status=status.HTTP_423_LOCKED,
            )
        return None
