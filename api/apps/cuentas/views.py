from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import Usuario
from .permissions import IsSuperAdmin
from .serializers import (
    CustomTokenObtainPairSerializer,
    OrganizadorCreateSerializer,
    OrganizadorListSerializer,
    OrganizadorUpdateSerializer,
)


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


class OrganizadorListCreateView(ListCreateAPIView):
    """
    GET  /api/admin/organizadores/  → Lista organizadores (rol dueño)
    POST /api/admin/organizadores/  → Crea un nuevo organizador

    Solo accesible por superadmin.
    """

    permission_classes = [IsSuperAdmin]

    def get_queryset(self):
        return Usuario.objects.filter(rol='dueno').order_by('-date_joined')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return OrganizadorCreateSerializer
        return OrganizadorListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        # Devolver datos del usuario creado con el serializer de lista
        output = OrganizadorListSerializer(user)
        return Response(output.data, status=status.HTTP_201_CREATED)


class OrganizadorDetailView(RetrieveUpdateDestroyAPIView):
    """
    GET    /api/admin/organizadores/<id>/  → Detalle de un organizador
    PATCH  /api/admin/organizadores/<id>/  → Editar organizador
    DELETE /api/admin/organizadores/<id>/  → Eliminar organizador

    Solo accesible por superadmin.
    """

    permission_classes = [IsSuperAdmin]

    def get_queryset(self):
        return Usuario.objects.filter(rol='dueno')

    def get_serializer_class(self):
        if self.request.method in ('PATCH', 'PUT'):
            return OrganizadorUpdateSerializer
        return OrganizadorListSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
