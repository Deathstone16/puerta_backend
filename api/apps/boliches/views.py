import logging
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.shortcuts import redirect
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cuentas.permissions import IsDueno

from .models import Boliche
from .serializers import BolicheSerializer

logger = logging.getLogger(__name__)


class BolichesView(APIView):
    """POST /api/boliches/ — Crear boliche (un dueño, un boliche)."""

    permission_classes = [IsDueno]

    def post(self, request):
        if Boliche.objects.filter(dueno=request.user).exists():
            return Response(
                {'error': 'Ya tenés un boliche registrado.'},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = BolicheSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(dueno=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BolicheMioView(APIView):
    """GET /api/boliches/mio/ — Obtener mi boliche."""

    permission_classes = [IsDueno]

    def get(self, request):
        try:
            boliche = Boliche.objects.get(dueno=request.user)
        except Boliche.DoesNotExist:
            return Response(
                {'error': 'No tenés ningún boliche registrado.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(BolicheSerializer(boliche).data)


class BolicheDetailView(APIView):
    """PATCH /api/boliches/:id/ — Editar boliche. DELETE bloqueado."""

    permission_classes = [IsDueno]

    def patch(self, request, pk):
        try:
            boliche = Boliche.objects.get(pk=pk)
        except Boliche.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if boliche.dueno != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = BolicheSerializer(boliche, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


# ─── OAuth Mercado Pago Marketplace ──────────────────────────────────────────

class MPConnectView(APIView):
    """
    GET /api/boliches/mp/connect/
    Redirige al dueño a la pantalla de autorización de Mercado Pago.
    El frontend llama a este endpoint y redirige al usuario.
    """

    permission_classes = [IsDueno]

    def get(self, request):
        params = urlencode({
            'client_id': settings.MP_APP_ID,
            'response_type': 'code',
            'platform_id': 'mp',
            'redirect_uri': settings.MP_REDIRECT_URI,
            'state': str(request.user.id),  # Para identificar al dueño en el callback
        })
        auth_url = f"https://auth.mercadopago.com.ar/authorization?{params}"

        return Response({'auth_url': auth_url})


class MPCallbackView(APIView):
    """
    GET /api/boliches/mp/callback/?code=...&state=...
    MP redirige acá después de que el dueño autoriza.
    Intercambia el code por access_token + refresh_token.
    """

    permission_classes = [AllowAny]  # MP redirige sin JWT

    def get(self, request):
        code = request.query_params.get('code')
        state = request.query_params.get('state')  # user_id del dueño

        if not code or not state:
            return Response(
                {'error': 'Parámetros code y state requeridos.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Intercambiar code por tokens
        try:
            token_data = _exchange_code_for_token(code)
        except MPOAuthError as e:
            logger.error("Error en OAuth MP: %s", e)
            # Redirigir al frontend con error
            return redirect(f"{settings.FRONTEND_URL}/dashboard?mp_error=true")

        # Buscar o crear el boliche del dueño
        try:
            from apps.cuentas.models import Usuario
            dueno = Usuario.objects.get(pk=int(state))
            boliche, _created = Boliche.objects.get_or_create(
                dueno=dueno,
                defaults={
                    'nombre': dueno.get_full_name() or dueno.username,
                    'direccion': '',
                },
            )
        except (Usuario.DoesNotExist, ValueError):
            return redirect(f"{settings.FRONTEND_URL}/dashboard?mp_error=true")

        # Guardar tokens en el boliche
        boliche.mp_access_token = token_data['access_token']
        boliche.mp_refresh_token = token_data['refresh_token']
        boliche.mp_user_id = str(token_data['user_id'])
        boliche.mp_connected_at = timezone.now()
        boliche.save(update_fields=[
            'mp_access_token', 'mp_refresh_token', 'mp_user_id', 'mp_connected_at',
        ])

        # Redirigir al frontend con éxito
        return redirect(f"{settings.FRONTEND_URL}/dashboard?mp_connected=true")


class MPOAuthError(Exception):
    pass


def _exchange_code_for_token(code: str) -> dict:
    """
    Intercambia el authorization code de MP por access_token + refresh_token.

    Returns:
        {'access_token': str, 'refresh_token': str, 'user_id': int, 'expires_in': int}
    """
    response = requests.post(
        'https://api.mercadopago.com/oauth/token',
        json={
            'client_id': settings.MP_APP_ID,
            'client_secret': settings.MP_CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': settings.MP_REDIRECT_URI,
        },
        headers={'Content-Type': 'application/json'},
        timeout=15,
    )

    if response.status_code != 200:
        raise MPOAuthError(f"MP OAuth error {response.status_code}: {response.text}")

    data = response.json()
    return {
        'access_token': data['access_token'],
        'refresh_token': data['refresh_token'],
        'user_id': data['user_id'],
        'expires_in': data.get('expires_in', 15552000),  # ~180 días por defecto
    }


def refresh_mp_token(boliche: Boliche) -> bool:
    """
    Renueva el access_token usando el refresh_token.
    Llamar periódicamente o cuando expire.

    Returns:
        True si se renovó exitosamente.
    """
    if not boliche.mp_refresh_token:
        return False

    response = requests.post(
        'https://api.mercadopago.com/oauth/token',
        json={
            'client_id': settings.MP_APP_ID,
            'client_secret': settings.MP_CLIENT_SECRET,
            'refresh_token': boliche.mp_refresh_token,
            'grant_type': 'refresh_token',
        },
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


class MPDisconnectView(APIView):
    """
    POST /api/boliches/mp/disconnect/
    Desconecta la cuenta de Mercado Pago del boliche del dueño.
    Limpia tokens y permite reconectar con otra cuenta.
    """

    permission_classes = [IsDueno]

    def post(self, request):
        try:
            boliche = Boliche.objects.get(dueno=request.user)
        except Boliche.DoesNotExist:
            return Response(
                {'error': 'No tenés ningún boliche registrado.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not boliche.mp_connected:
            return Response(
                {'error': 'No hay cuenta de Mercado Pago conectada.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        boliche.mp_access_token = None
        boliche.mp_refresh_token = None
        boliche.mp_user_id = None
        boliche.mp_connected_at = None
        boliche.save(update_fields=[
            'mp_access_token', 'mp_refresh_token', 'mp_user_id', 'mp_connected_at',
        ])

        return Response({'mensaje': 'Cuenta de Mercado Pago desconectada correctamente.'})
