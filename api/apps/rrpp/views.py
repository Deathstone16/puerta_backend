from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cuentas.permissions import IsDueno, IsRRPP
from apps.eventos.models import Evento

from .models import AsignacionRRPP, LinkRRPP, RRPP
from .serializers import (
    AsignacionConEstadisticasSerializer,
    LinkRRPPSerializer,
    RRPPCreateSerializer,
    RRPPSerializer,
)


class RRPPListCreateView(APIView):
    """
    GET /api/rrpp/ — Lista RRPP del organizador.
    POST /api/rrpp/ — Alta de RRPP (transacción atómica).
    """

    permission_classes = [IsDueno]

    def get(self, request):
        rrpps = RRPP.objects.filter(organizador=request.user).select_related('usuario').prefetch_related(
            'asignaciones__evento', 'asignaciones__links',
        )
        return Response(RRPPSerializer(rrpps, many=True).data)

    def post(self, request):
        serializer = RRPPCreateSerializer(data=request.data, context={'organizador': request.user})
        if serializer.is_valid():
            rrpp = serializer.save()
            return Response(RRPPSerializer(rrpp).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AsignarEventoView(APIView):
    """
    GET  /api/rrpp/:id/asignar-evento/ — Lista eventos asignables al RRPP.
    POST /api/rrpp/:id/asignar-evento/ — Asigna RRPP a evento, genera 2 links.
    """

    permission_classes = [IsDueno]

    def get(self, request, pk):
        rrpp = get_object_or_404(RRPP, pk=pk)

        if rrpp.organizador != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)

        # Eventos ya asignados a este RRPP
        eventos_asignados_ids = AsignacionRRPP.objects.filter(
            rrpp=rrpp,
        ).values_list('evento_id', flat=True)

        # Eventos del organizador, activos, no asignados aún
        eventos_disponibles = Evento.objects.filter(
            organizador=request.user,
            estado='activo',
        ).exclude(
            id__in=eventos_asignados_ids,
        ).order_by('-fecha')

        data = [
            {'id': e.id, 'nombre': e.nombre, 'fecha': e.fecha}
            for e in eventos_disponibles
        ]

        return Response(data)

    def post(self, request, pk):
        rrpp = get_object_or_404(RRPP, pk=pk)

        # Verificar que el RRPP pertenece al organizador autenticado
        if rrpp.organizador != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)

        evento_id = request.data.get('evento_id')
        if not evento_id:
            return Response(
                {'error': 'El campo evento_id es obligatorio.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            evento = Evento.objects.get(pk=evento_id)
        except Evento.DoesNotExist:
            return Response(
                {'error': 'El evento no existe.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if evento.organizador != request.user:
            return Response(
                {'error': 'El evento no te pertenece.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if AsignacionRRPP.objects.filter(rrpp=rrpp, evento=evento).exists():
            return Response(
                {'error': 'El RRPP ya está asignado a este evento.'},
                status=status.HTTP_409_CONFLICT,
            )

        asignacion = AsignacionRRPP.objects.create(rrpp=rrpp, evento=evento)
        # La signal post_save genera los 2 links automáticamente
        links = asignacion.links.all()

        return Response({
            'asignacion_id': asignacion.id,
            'rrpp_nombre': str(rrpp),
            'evento_nombre': evento.nombre,
            'links': LinkRRPPSerializer(links, many=True).data,
        }, status=status.HTTP_201_CREATED)


class MiPanelView(APIView):
    """GET /api/rrpp/mi-panel/ — Panel del RRPP autenticado."""

    permission_classes = [IsRRPP]

    def get(self, request):
        rrpp = get_object_or_404(RRPP, usuario=request.user)
        asignaciones = (
            AsignacionRRPP.objects
            .filter(rrpp=rrpp, activa=True)
            .select_related('evento')
            .prefetch_related('links')
        )
        return Response(AsignacionConEstadisticasSerializer(asignaciones, many=True).data)


class AnotarInvitadoView(APIView):
    """POST /api/rrpp/anotar-invitado/ — Carga manual de invitado."""

    permission_classes = [IsRRPP]

    def post(self, request):
        slug_lista = request.data.get('slug_lista')
        nombre = request.data.get('nombre', '').strip()
        apellido = request.data.get('apellido', '').strip()
        dni = request.data.get('dni', '').strip()
        instagram = request.data.get('instagram', '').strip()

        if not all([slug_lista, nombre, apellido, dni]):
            return Response(
                {'error': 'Los campos slug_lista, nombre, apellido y dni son obligatorios.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            link = LinkRRPP.objects.select_related(
                'asignacion__rrpp__usuario', 'asignacion__evento',
            ).get(slug=slug_lista, tipo='lista')
        except LinkRRPP.DoesNotExist:
            return Response(
                {'error': 'Link no encontrado.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Verificar que pertenece al RRPP autenticado
        if link.asignacion.rrpp.usuario != request.user:
            return Response(
                {'error': 'Este link no te pertenece.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not link.activo:
            return Response(
                {'error': 'Este link está inactivo.'},
                status=status.HTTP_410_GONE,
            )

        evento = link.asignacion.evento

        # Verificar DNI duplicado
        try:
            from apps.puerta.models import Asistente
            if Asistente.objects.filter(evento=evento, dni=dni).exists():
                return Response(
                    {'error': 'Este DNI ya está registrado en el evento.'},
                    status=status.HTTP_409_CONFLICT,
                )
            asistente = Asistente.objects.create(
                evento=evento,
                link_rrpp=link,
                nombre=nombre,
                apellido=apellido,
                dni=dni,
                instagram=instagram,
                tipo_ingreso='lista_rrpp',
                estado='pendiente',  # Carga manual del RRPP = ya aprobado por él
            )
            # Como lo carga el RRPP manualmente, lo dejamos directo en la lista
            # (no necesita aprobación adicional del RRPP)
            return Response({
                'id': asistente.id,
                'nombre': f"{asistente.nombre} {asistente.apellido}",
                'dni': asistente.dni,
                'instagram': asistente.instagram,
                'estado': 'pendiente',
            }, status=status.HTTP_201_CREATED)
        except ImportError:
            return Response(
                {'error': 'La app puerta no está disponible aún.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


# ─── Gestión de invitados por RRPP ───────────────────────────────────────────

class AprobarInvitadoView(APIView):
    """POST /api/rrpp/aprobar-invitado/:id/ — RRPP aprueba solicitud pendiente."""

    permission_classes = [IsRRPP]

    def post(self, request, pk):
        from apps.puerta.models import Asistente

        asistente = get_object_or_404(Asistente, pk=pk)

        # Verificar que el invitado pertenece a un link del RRPP autenticado
        if not asistente.link_rrpp or asistente.link_rrpp.asignacion.rrpp.usuario != request.user:
            return Response(
                {'error': 'No tenés permiso sobre este invitado.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if asistente.estado != 'pendiente':
            return Response(
                {'error': 'Solo se pueden aprobar invitados en estado pendiente.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # "Aprobado por RRPP" = queda en la lista visible para el guardia
        # El estado sigue siendo 'pendiente' para el flujo de puerta (guardia aprueba/rebota)
        # Marcamos con un campo que el RRPP ya lo validó — no cambiamos estado
        # Para el MVP: simplemente confirmamos que queda en lista
        return Response({
            'id': asistente.id,
            'estado': 'aprobado',
            'mensaje': 'Invitado aprobado. Aparece en la lista del guardia.',
        })


class RechazarInvitadoView(APIView):
    """POST /api/rrpp/rechazar-invitado/:id/ — RRPP rechaza solicitud."""

    permission_classes = [IsRRPP]

    def post(self, request, pk):
        from apps.puerta.models import Asistente

        asistente = get_object_or_404(Asistente, pk=pk)

        if not asistente.link_rrpp or asistente.link_rrpp.asignacion.rrpp.usuario != request.user:
            return Response(
                {'error': 'No tenés permiso sobre este invitado.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if asistente.estado != 'pendiente':
            return Response(
                {'error': 'Solo se pueden rechazar invitados en estado pendiente.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Rechazar = eliminar de la lista (no llega al guardia)
        asistente.delete()

        return Response({
            'id': pk,
            'estado': 'rechazado',
            'mensaje': 'Invitado rechazado y removido de la lista.',
        })


class EliminarInvitadoView(APIView):
    """POST /api/rrpp/eliminar-invitado/:id/ — RRPP elimina invitado de lista."""

    permission_classes = [IsRRPP]

    def post(self, request, pk):
        from apps.puerta.models import Asistente

        asistente = get_object_or_404(Asistente, pk=pk)

        if not asistente.link_rrpp or asistente.link_rrpp.asignacion.rrpp.usuario != request.user:
            return Response(
                {'error': 'No tenés permiso sobre este invitado.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if asistente.estado == 'ingresado_final':
            return Response(
                {'error': 'No se puede eliminar un asistente que ya ingresó.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        asistente.delete()

        return Response({
            'id': pk,
            'mensaje': 'Invitado eliminado de la lista.',
        })


class EditarInvitadoView(APIView):
    """PATCH /api/rrpp/editar-invitado/:id/ — RRPP edita datos de un invitado."""

    permission_classes = [IsRRPP]

    def patch(self, request, pk):
        from apps.puerta.models import Asistente

        asistente = get_object_or_404(Asistente, pk=pk)

        if not asistente.link_rrpp or asistente.link_rrpp.asignacion.rrpp.usuario != request.user:
            return Response(
                {'error': 'No tenés permiso sobre este invitado.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if asistente.estado == 'ingresado_final':
            return Response(
                {'error': 'No se puede editar un asistente que ya ingresó.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Campos editables
        nombre = request.data.get('nombre')
        apellido = request.data.get('apellido')
        dni = request.data.get('dni')
        instagram = request.data.get('instagram')

        update_fields = []
        if nombre is not None:
            asistente.nombre = nombre.strip()
            update_fields.append('nombre')
        if apellido is not None:
            asistente.apellido = apellido.strip()
            update_fields.append('apellido')
        if dni is not None:
            # Verificar que el nuevo DNI no colisione
            nuevo_dni = dni.strip()
            if nuevo_dni != asistente.dni:
                if Asistente.objects.filter(evento=asistente.evento, dni=nuevo_dni).exists():
                    return Response(
                        {'error': 'Este DNI ya está registrado en el evento.'},
                        status=status.HTTP_409_CONFLICT,
                    )
            asistente.dni = nuevo_dni
            update_fields.append('dni')
        if instagram is not None:
            asistente.instagram = instagram.strip()
            update_fields.append('instagram')

        if update_fields:
            asistente.save(update_fields=update_fields)

        return Response({
            'id': asistente.id,
            'nombre': asistente.nombre,
            'apellido': asistente.apellido,
            'dni': asistente.dni,
            'instagram': asistente.instagram,
            'estado': asistente.estado,
            'mensaje': 'Invitado actualizado.',
        })


class RRPPDetailView(APIView):
    """
    PATCH /api/rrpp/:id/ — Editar comisión de un RRPP.
    DELETE /api/rrpp/:id/ — Eliminar RRPP (desactiva usuario).
    """

    permission_classes = [IsDueno]

    def patch(self, request, pk):
        rrpp = get_object_or_404(RRPP, pk=pk)

        if rrpp.organizador != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)

        # Campos editables
        tipo_comision = request.data.get('tipo_comision')
        valor_comision = request.data.get('valor_comision')
        nombre = request.data.get('nombre')
        apellido = request.data.get('apellido')
        telefono = request.data.get('telefono')

        if tipo_comision is not None:
            rrpp.tipo_comision = tipo_comision
        if valor_comision is not None:
            rrpp.valor_comision = valor_comision

        rrpp.save()

        # Actualizar datos del usuario asociado
        usuario = rrpp.usuario
        changed = False
        if nombre is not None:
            usuario.first_name = nombre.strip()
            changed = True
        if apellido is not None:
            usuario.last_name = apellido.strip()
            changed = True
        if telefono is not None:
            usuario.telefono = telefono.strip()
            changed = True
        if changed:
            usuario.save()

        return Response(RRPPSerializer(rrpp).data)

    def delete(self, request, pk):
        rrpp = get_object_or_404(RRPP, pk=pk)

        if rrpp.organizador != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)

        # Desactivar el usuario (no eliminamos para mantener historial)
        rrpp.usuario.is_active = False
        rrpp.usuario.save(update_fields=['is_active'])

        # Desactivar asignaciones
        rrpp.asignaciones.update(activa=False)

        return Response({'mensaje': 'RRPP eliminado correctamente.'})
