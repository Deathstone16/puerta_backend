"""
Servicios de negocio de pagos.
Funciones puras importables por otras apps sin dependencias circulares.
"""
import logging

from .mp_client import MPError, reembolsar_pago

logger = logging.getLogger(__name__)


def reembolsar_evento(evento_id: int) -> int:
    """
    Reembolsa todas las compras web de un evento cancelado.
    Llamada por apps.eventos al cancelar un evento.

    Returns:
        Número de reembolsos procesados exitosamente.
    """
    from apps.puerta.models import Asistente

    asistentes_web = Asistente.objects.filter(
        evento_id=evento_id,
        tipo_ingreso='web_anticipada',
        mp_payment_id__isnull=False,
    )

    exitosos = 0
    for asistente in asistentes_web:
        try:
            ok = reembolsar_pago(
                payment_id=asistente.mp_payment_id,
                idempotency_key=f"refund-{asistente.id}",
            )
            if ok:
                exitosos += 1
        except MPError as e:
            logger.error(
                "Error al reembolsar asistente %s (payment_id=%s): %s",
                asistente.id, asistente.mp_payment_id, e,
            )

    return exitosos
