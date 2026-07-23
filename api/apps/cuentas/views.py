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


# ─── Staff Management (Guardias y Cajeras) ───────────────────────────────────

from django.shortcuts import get_object_or_404
from django.db import transaction

from .permissions import IsDueno
from .models import AsignacionStaff


class StaffListCreateView(ListCreateAPIView):
    """
    GET  /api/staff/ — Lista guardias y cajeras del organizador.
    POST /api/staff/ — Crear guardia o cajera.
    """

    permission_classes = [IsDueno]

    def get_queryset(self):
        return Usuario.objects.filter(
            organizador=self.request.user,
            rol__in=['guardia', 'cajera'],
            is_active=True,
        ).prefetch_related('asignaciones_staff__evento').order_by('-date_joined')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return StaffCreateSerializer
        return StaffListSerializer

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        data = []
        for user in qs:
            asignaciones = user.asignaciones_staff.filter(activa=True)
            data.append({
                'id': user.id,
                'nombre': user.get_full_name() or user.username,
                'username': user.username,
                'rol': user.rol,
                'eventos_asignados': asignaciones.count(),
                'eventos': [
                    {'id': a.evento.id, 'nombre': a.evento.nombre}
                    for a in asignaciones.select_related('evento')
                ],
            })
        return Response(data)

    def create(self, request, *args, **kwargs):
        nombre = request.data.get('nombre', '').strip()
        apellido = request.data.get('apellido', '').strip()
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '')
        rol = request.data.get('rol', '').strip()

        if not all([nombre, apellido, username, password, rol]):
            return Response(
                {'error': 'Los campos nombre, apellido, username, password y rol son obligatorios.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if rol not in ('guardia', 'cajera'):
            return Response(
                {'error': 'El rol debe ser "guardia" o "cajera".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if Usuario.objects.filter(username=username).exists():
            return Response(
                {'error': 'Este username ya existe.'},
                status=status.HTTP_409_CONFLICT,
            )

        with transaction.atomic():
            user = Usuario.objects.create_user(
                username=username,
                password=password,
                first_name=nombre,
                last_name=apellido,
                rol=rol,
                organizador=request.user,
            )

        return Response({
            'id': user.id,
            'nombre': user.get_full_name(),
            'username': user.username,
            'rol': user.rol,
            'eventos_asignados': 0,
            'eventos': [],
        }, status=status.HTTP_201_CREATED)


class StaffDetailView(RetrieveUpdateDestroyAPIView):
    """
    PATCH  /api/staff/:id/ — Editar nombre/apellido del staff.
    DELETE /api/staff/:id/ — Desactivar staff.
    """

    permission_classes = [IsDueno]

    def get_queryset(self):
        return Usuario.objects.filter(
            organizador=self.request.user,
            rol__in=['guardia', 'cajera'],
        )

    def patch(self, request, *args, **kwargs):
        user = self.get_object()
        nombre = request.data.get('nombre')
        apellido = request.data.get('apellido')

        if nombre is not None:
            user.first_name = nombre.strip()
        if apellido is not None:
            user.last_name = apellido.strip()
        user.save()

        return Response({
            'id': user.id,
            'nombre': user.get_full_name(),
            'username': user.username,
            'rol': user.rol,
        })

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        user.is_active = False
        user.save(update_fields=['is_active'])
        AsignacionStaff.objects.filter(usuario=user).update(activa=False)
        return Response({'mensaje': 'Staff desactivado correctamente.'})


class StaffAsignarEventoView(ListCreateAPIView):
    """
    GET  /api/staff/:id/asignar-evento/ — Eventos disponibles para asignar.
    POST /api/staff/:id/asignar-evento/ — Asignar staff a evento.
    """

    permission_classes = [IsDueno]

    def get(self, request, pk):
        user = get_object_or_404(Usuario, pk=pk, organizador=request.user)
        from apps.eventos.models import Evento

        asignados_ids = AsignacionStaff.objects.filter(
            usuario=user, activa=True,
        ).values_list('evento_id', flat=True)

        eventos = Evento.objects.filter(
            organizador=request.user, estado='activo',
        ).exclude(id__in=asignados_ids).order_by('-fecha')

        return Response([
            {'id': e.id, 'nombre': e.nombre, 'fecha': e.fecha}
            for e in eventos
        ])

    def post(self, request, pk):
        user = get_object_or_404(Usuario, pk=pk, organizador=request.user)
        from apps.eventos.models import Evento

        evento_id = request.data.get('evento_id')
        if not evento_id:
            return Response(
                {'error': 'El campo evento_id es obligatorio.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            evento = Evento.objects.get(pk=evento_id, organizador=request.user)
        except Evento.DoesNotExist:
            return Response(
                {'error': 'El evento no existe o no te pertenece.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing = AsignacionStaff.objects.filter(usuario=user, evento=evento).first()
        if existing and existing.activa:
            return Response({
                'mensaje': f'{user.get_full_name()} ya está asignado a {evento.nombre}.',
                'ya_asignado': True,
            })

        if existing and not existing.activa:
            existing.activa = True
            existing.save(update_fields=['activa'])
            asignacion = existing
        else:
            asignacion = AsignacionStaff.objects.create(
                usuario=user, evento=evento, rol=user.rol,
            )

        return Response({
            'asignacion_id': asignacion.id,
            'staff_nombre': user.get_full_name(),
            'evento_nombre': evento.nombre,
            'rol': user.rol,
        }, status=status.HTTP_201_CREATED)


# Dummy serializers referenced above (inline since they're simple)
from rest_framework import serializers as _s

class StaffListSerializer(_s.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ['id', 'first_name', 'last_name', 'username', 'rol']

class StaffCreateSerializer(_s.Serializer):
    nombre = _s.CharField()
    apellido = _s.CharField()
    username = _s.CharField()
    password = _s.CharField()
    rol = _s.ChoiceField(choices=['guardia', 'cajera'])
