"""
Wrapper del SDK de Mercado Pago — Marketplace con Split Payments.
Toda la interacción con la API de MP pasa por este módulo.
"""
import logging

import mercadopago
from django.conf import settings

logger = logging.getLogger(__name__)


class MPError(Exception):
    """Error al interactuar con la API de Mercado Pago."""
    pass


def _get_sdk():
    """SDK con el access token de la app Norware (para operaciones propias)."""
    return mercadopago.SDK(settings.MP_ACCESS_TOKEN)


def _get_seller_sdk(boliche):
    """
    SDK con el access token del vendedor (dueño del boliche).
    Requiere que el boliche tenga mp_access_token (OAuth conectado).
    """
    if not boliche.mp_access_token:
        raise MPError("El boliche no tiene Mercado Pago conectado.")
    return mercadopago.SDK(boliche.mp_access_token)


def crear_preferencia(evento, comprador: dict) -> dict:
    """
    Crea una preferencia de pago usando el access_token del vendedor (split payment).

    El pago se deposita en la cuenta del dueño.
    Norware retiene marketplace_fee como comisión.

    Args:
        evento: instancia de Evento (con boliche.mp_access_token)
        comprador: {'nombre': str, 'apellido': str, 'email': str, 'dni': str}

    Returns:
        {'init_point': str, 'preference_id': str}

    Raises:
        MPError: si la API de MP devuelve error o el boliche no está conectado
    """
    from apps.eventos.utils import calcular_precio_publicado

    boliche = evento.boliche

    if not boliche.mp_connected:
        raise MPError("El organizador no conectó su cuenta de Mercado Pago.")

    desglose = calcular_precio_publicado(evento.precio_base)
    fee_norware = round(float(evento.precio_base) * settings.NORWARE_FEE_PCT / 100, 2)

    preference_data = {
        'items': [{
            'title': evento.nombre,
            'quantity': 1,
            'unit_price': desglose['precio_publicado'],
            'currency_id': 'ARS',
        }],
        'payer': {
            'name': comprador['nombre'],
            'surname': comprador['apellido'],
            'email': comprador['email'],
        },
        'marketplace_fee': fee_norware,
        'back_urls': {
            'success': f"{settings.FRONTEND_URL}/wallet/pendiente",
            'failure': f"{settings.FRONTEND_URL}/checkout/error",
            'pending': f"{settings.FRONTEND_URL}/wallet/pendiente",
        },
        'notification_url': f"{settings.BACKEND_URL}/api/pagos/webhook/",
        'external_reference': f"evento-{evento.id}-dni-{comprador['dni']}",
        'metadata': {
            'evento_id': evento.id,
            'dni': comprador['dni'],
            'nombre': comprador['nombre'],
            'apellido': comprador['apellido'],
        },
    }

    # Usar el SDK del vendedor para que el pago vaya a su cuenta
    sdk = _get_seller_sdk(boliche)
    response = sdk.preference().create(preference_data)

    if response['status'] not in (200, 201):
        raise MPError(f"Error MP {response['status']}: {response.get('response', {})}")

    return {
        'init_point': response['response']['init_point'],
        'preference_id': response['response']['id'],
    }


def obtener_pago(payment_id: str) -> dict:
    """Obtiene los datos de un pago por su ID (usando token de Norware)."""
    sdk = _get_sdk()
    response = sdk.payment().get(payment_id)
    if response['status'] != 200:
        raise MPError(f"Error al obtener pago {payment_id}: status {response['status']}")
    return response['response']


def reembolsar_pago(payment_id: str, idempotency_key: str) -> bool:
    """
    Solicita el reembolso total de un pago (usando token de Norware).
    Devuelve True si fue exitoso.
    """
    sdk = _get_sdk()
    response = sdk.refund().create(
        payment_id,
        request_options={'custom_headers': {'x-idempotency-key': idempotency_key}},
    )
    return response['status'] in (200, 201)
