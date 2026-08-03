"""
Wrapper del SDK de Mercado Pago — Marketplace con Split Payments.
Toda la interacción con la API de MP pasa por este módulo.
"""
import logging

import mercadopago
import requests
from django.conf import settings
from django.utils import timezone

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


def refrescar_token(boliche) -> bool:
    """
    Renueva el access_token del vendedor usando su refresh_token (OAuth).
    El access_token de MP vence (~180 días): hay que renovarlo antes de que
    expire o las llamadas a la API devuelven 401 "invalid access token".

    Returns:
        True si se renovó con éxito y se guardó en el boliche.
    """
    if not boliche.mp_refresh_token:
        return False

    payload = {
        'client_id': settings.MP_APP_ID,
        'client_secret': settings.MP_CLIENT_SECRET,
        'refresh_token': boliche.mp_refresh_token,
        'grant_type': 'refresh_token',
    }
    if settings.MP_TEST_MODE:
        payload['test_token'] = True

    response = requests.post(
        'https://api.mercadopago.com/oauth/token',
        json=payload,
        headers={'Content-Type': 'application/json'},
        timeout=15,
    )

    if response.status_code != 200:
        logger.error("Error renovando token MP para boliche %s: %s", boliche.id, response.text)
        return False

    data = response.json()
    boliche.mp_access_token = data['access_token']
    boliche.mp_refresh_token = data['refresh_token']
    boliche.mp_connected_at = timezone.now()
    boliche.save(update_fields=['mp_access_token', 'mp_refresh_token', 'mp_connected_at'])
    return True


def crear_preferencia(evento, comprador: dict, link_slug: str | None = None) -> dict:
    """
    Crea una preferencia de pago usando el access_token del vendedor (split payment).

    El pago se deposita en la cuenta del dueño.
    Norware retiene marketplace_fee como comisión.

    Args:
        evento: instancia de Evento (con boliche.mp_access_token)
        comprador: {'nombre': str, 'apellido': str, 'email': str, 'dni': str}
        link_slug: slug del LinkRRPP que originó la compra (para atribuir la venta al RRPP)

    Returns:
        {'init_point': str, 'preference_id': str}

    Raises:
        MPError: si la API de MP devuelve error o el boliche no está conectado
    """
    from apps.eventos.utils import calcular_precio_publicado

    # El evento puede haberse creado antes de que el dueño conectara MP (y entonces
    # quedó sin boliche). Como fallback usamos el boliche del organizador, así los
    # eventos viejos también pueden cobrar una vez que el dueño conecta Mercado Pago.
    boliche = evento.boliche
    if boliche is None and evento.organizador_id:
        boliche = evento.organizador.boliches.first()

    # Sin boliche no hay cuenta de MP del vendedor: MPError, no un crash (evita el 500).
    if boliche is None:
        raise MPError("El evento no tiene un boliche con Mercado Pago conectado.")

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
            'identification': {
                'type': 'DNI',
                'number': comprador['dni'],
            },
        },
        #'marketplace_fee': fee_norware,
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
            'link_slug': link_slug or '',
        },
    }

    # Usar el SDK del vendedor para que el pago vaya a su cuenta
    sdk = _get_seller_sdk(boliche)
    response = sdk.preference().create(preference_data)

    # Access token vencido/inválido (401): renovar con el refresh_token y reintentar una vez
    if response['status'] == 401 and refrescar_token(boliche):
        logger.info("Token MP del boliche %s renovado, reintentando preferencia...", boliche.id)
        sdk = _get_seller_sdk(boliche)
        response = sdk.preference().create(preference_data)

    if response['status'] not in (200, 201):
        if response['status'] == 401:
            raise MPError(
                "El Mercado Pago del organizador está vencido o no es válido. "
                "Reconectá su cuenta desde el dashboard."
            )
        raise MPError(f"Error MP {response['status']}: {response.get('response', {})}")

    return {
        'init_point': response['response']['init_point'],
        'preference_id': response['response']['id'],
    }


def _iterar_sdks():
    """
    Genera los SDKs a probar para operar sobre un pago: primero el de la app
    (Norware) y después el de cada boliche con MP conectado.

    En modo de pruebas el token de la app puede no poder leer/reembolsar pagos
    de un vendedor de prueba, pero el access_token del propio vendedor siempre
    puede operar sobre sus pagos. Así el webhook funciona en test y producción.
    """
    yield _get_sdk()
    from apps.boliches.models import Boliche

    boliches = Boliche.objects.filter(
        mp_access_token__isnull=False,
        mp_user_id__isnull=False,
    )
    for boliche in boliches:
        yield _get_seller_sdk(boliche)


def obtener_pago(payment_id: str) -> dict:
    """
    Obtiene los datos de un pago por su ID.

    Prueba primero con el token de la app; si falla, con el token de cada
    boliche conectado (el vendedor siempre puede leer sus propios pagos).
    """
    errores = []
    for sdk in _iterar_sdks():
        try:
            response = sdk.payment().get(payment_id)
            if response['status'] == 200:
                return response['response']
            errores.append(f"status {response['status']}")
        except Exception as e:  # noqa: BLE001
            errores.append(str(e))
    raise MPError(f"Error al obtener pago {payment_id}: {'; '.join(errores) or 'sin respuesta'}")


def reembolsar_pago(payment_id: str, idempotency_key: str) -> bool:
    """
    Solicita el reembolso total de un pago.

    Prueba primero con el token de la app; si falla, con el token de cada
    boliche conectado. Devuelve True si fue exitoso.
    """
    for sdk in _iterar_sdks():
        try:
            response = sdk.refund().create(
                payment_id,
                request_options={'custom_headers': {'x-idempotency-key': idempotency_key}},
            )
            if response['status'] in (200, 201):
                return True
        except Exception:  # noqa: BLE001
            continue
    return False
