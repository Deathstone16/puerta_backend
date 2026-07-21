from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import CustomTokenObtainPairSerializer


class LoginView(TokenObtainPairView):
    """
    POST /api/auth/login/

    Autentica un usuario y devuelve tokens JWT con el campo 'rol' incluido
    tanto en el payload del token como en el cuerpo de la respuesta.

    Rate limit: 5 intentos por minuto por IP (scope 'login').

    Request:
        { "username": "...", "password": "..." }

    Response 200:
        { "access": "...", "refresh": "...", "rol": "...", "nombre": "...", "id": N }
    """

    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'
