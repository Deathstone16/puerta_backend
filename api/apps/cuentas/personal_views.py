from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cuentas.models import AsignacionStaff, Usuario
from apps.cuentas.permissions import IsDueno
from apps.rrpp.models import RRPP


class PersonalListCreateView(APIView):
    """
    GET  /api/personal/ — Returns all personnel (RRPP + guards + cashiers) for the owner.
    POST /api/personal/ — Create new personnel of any role.
    """

    permission_classes = [IsDueno]

    def get(self, request):
        result = []

        # Get RRPP created by this organizer
        rrpps = RRPP.objects.filter(
            organizador=request.user, usuario__is_active=True,
        ).select_related('usuario').prefetch_related('asignaciones__evento')

        for rrpp in rrpps:
            asignaciones = rrpp.asignaciones.filter(activa=True)
            result.append({
                'id': rrpp.usuario.id,
                'rrpp_id': rrpp.id,
                'nombre': rrpp.usuario.get_full_name() or rrpp.usuario.username,
                'username': rrpp.usuario.username,
                'rol': 'rrpp',
                'eventos_asignados': asignaciones.count(),
                'eventos': [
                    {
                        'id': a.evento.id,
                        'nombre': a.evento.nombre,
                        'tipo_comision': a.tipo_comision,
                        'valor_comision': float(a.valor_comision),
                    }
                    for a in asignaciones.select_related('evento')
                ],
            })

        # Get guards and cashiers created by this organizer
        staff = Usuario.objects.filter(
            organizador=request.user,
            rol__in=['guardia', 'cajera'],
            is_active=True,
        ).prefetch_related('asignaciones_staff__evento')

        for user in staff:
            asignaciones = user.asignaciones_staff.filter(activa=True)
            result.append({
                'id': user.id,
                'rrpp_id': None,
                'nombre': user.get_full_name() or user.username,
                'username': user.username,
                'rol': user.rol,
                'eventos_asignados': asignaciones.count(),
                'eventos': [
                    {
                        'id': a.evento.id,
                        'nombre': a.evento.nombre,
                    }
                    for a in asignaciones.select_related('evento')
                ],
            })

        # Sort by name
        result.sort(key=lambda x: x['nombre'].lower())
        return Response(result)

    def post(self, request):
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

        if rol not in ('rrpp', 'guardia', 'cajera'):
            return Response(
                {'error': 'El rol debe ser "rrpp", "guardia" o "cajera".'},
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

            # If RRPP, also create the RRPP model instance
            if rol == 'rrpp':
                RRPP.objects.create(
                    usuario=user,
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


class PersonalAsignarEventoView(APIView):
    """POST /api/personal/:id/asignar-evento/ — Assign personnel to an event."""

    permission_classes = [IsDueno]

    def post(self, request, pk):
        from apps.eventos.models import Evento

        user = get_object_or_404(Usuario, pk=pk)

        # Verify this person belongs to the requesting owner
        if user.rol == 'rrpp':
            rrpp = RRPP.objects.filter(usuario=user, organizador=request.user).first()
            if not rrpp:
                return Response(status=status.HTTP_403_FORBIDDEN)
        else:
            if user.organizador != request.user:
                return Response(status=status.HTTP_403_FORBIDDEN)

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

        if user.rol == 'rrpp':
            # RRPP assignment requires commission
            tipo_comision = request.data.get('tipo_comision')
            valor_comision = request.data.get('valor_comision')

            if not tipo_comision or valor_comision is None:
                return Response(
                    {'error': 'Los campos tipo_comision y valor_comision son obligatorios para RRPP.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if tipo_comision not in ('fijo', 'porcentaje'):
                return Response(
                    {'error': 'tipo_comision debe ser "fijo" o "porcentaje".'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                valor_comision = float(valor_comision)
            except (TypeError, ValueError):
                return Response(
                    {'error': 'valor_comision debe ser un número.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            from apps.rrpp.models import AsignacionRRPP
            existing = AsignacionRRPP.objects.filter(rrpp=rrpp, evento=evento).first()
            if existing and existing.activa:
                return Response({
                    'mensaje': f'{user.get_full_name()} ya está asignado a {evento.nombre}.',
                    'ya_asignado': True,
                })
            if existing and not existing.activa:
                existing.activa = True
                existing.tipo_comision = tipo_comision
                existing.valor_comision = valor_comision
                existing.save(update_fields=['activa', 'tipo_comision', 'valor_comision'])
            else:
                AsignacionRRPP.objects.create(
                    rrpp=rrpp, evento=evento,
                    tipo_comision=tipo_comision, valor_comision=valor_comision,
                )

        else:
            # Guard/Cashier assignment — no commission
            existing = AsignacionStaff.objects.filter(usuario=user, evento=evento).first()
            if existing and existing.activa:
                return Response({
                    'mensaje': f'{user.get_full_name()} ya está asignado a {evento.nombre}.',
                    'ya_asignado': True,
                })
            if existing and not existing.activa:
                existing.activa = True
                existing.save(update_fields=['activa'])
            else:
                AsignacionStaff.objects.create(
                    usuario=user, evento=evento, rol=user.rol,
                )

        return Response({
            'staff_nombre': user.get_full_name(),
            'evento_nombre': evento.nombre,
            'rol': user.rol,
        }, status=status.HTTP_201_CREATED)


class PersonalDetailView(APIView):
    """
    PATCH  /api/personal/:id/ — Edit name.
    DELETE /api/personal/:id/ — Deactivate personnel.
    """

    permission_classes = [IsDueno]

    def _get_personal(self, request, pk):
        user = get_object_or_404(Usuario, pk=pk)
        if user.rol == 'rrpp':
            if not RRPP.objects.filter(usuario=user, organizador=request.user).exists():
                return None
        else:
            if user.organizador != request.user:
                return None
        return user

    def patch(self, request, pk):
        user = self._get_personal(request, pk)
        if not user:
            return Response(status=status.HTTP_403_FORBIDDEN)

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

    def delete(self, request, pk):
        user = self._get_personal(request, pk)
        if not user:
            return Response(status=status.HTTP_403_FORBIDDEN)

        user.is_active = False
        user.save(update_fields=['is_active'])

        # Deactivate all assignments
        if user.rol == 'rrpp':
            rrpp = RRPP.objects.filter(usuario=user).first()
            if rrpp:
                from apps.rrpp.models import AsignacionRRPP
                AsignacionRRPP.objects.filter(rrpp=rrpp).update(activa=False)
        else:
            AsignacionStaff.objects.filter(usuario=user).update(activa=False)

        return Response({'mensaje': 'Personal desactivado correctamente.'})
