from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from .models import AsignacionRRPP, LinkRRPP, RRPP

User = get_user_model()


class LinkRRPPSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = LinkRRPP
        fields = ['tipo', 'slug', 'activo', 'url']

    def get_url(self, obj):
        if obj.tipo == 'lista':
            return f"/lista/{obj.slug}/"
        return f"/venta/{obj.slug}/"


class AsignacionConEstadisticasSerializer(serializers.ModelSerializer):
    links = LinkRRPPSerializer(many=True, read_only=True)
    evento_id = serializers.IntegerField(source='evento.id', read_only=True)
    evento_nombre = serializers.CharField(source='evento.nombre', read_only=True)
    evento_fecha = serializers.DateTimeField(source='evento.fecha', read_only=True)
    color_pulsera = serializers.CharField(source='evento.color_pulsera', read_only=True)
    estadisticas = serializers.SerializerMethodField()

    class Meta:
        model = AsignacionRRPP
        fields = [
            'id', 'evento_id', 'evento_nombre', 'evento_fecha',
            'color_pulsera', 'activa', 'links', 'estadisticas',
        ]

    def get_estadisticas(self, asignacion):
        try:
            from apps.puerta.models import Asistente
            qs = Asistente.objects.filter(link_rrpp__asignacion=asignacion)
            invitados_recientes = list(
                qs.order_by('-created_at')[:20].values(
                    'id', 'nombre', 'apellido', 'dni', 'instagram', 'estado', 'created_at',
                )
            )
            return {
                'anotados': qs.count(),
                'ingresados': qs.filter(estado='ingresado_final').count(),
                'pendientes': qs.filter(estado__in=['pendiente', 'aprobado_guardia']).count(),
                'rebotados': qs.filter(estado='rebotado_guardia').count(),
                'invitados_recientes': invitados_recientes,
            }
        except Exception:
            return {'anotados': 0, 'ingresados': 0, 'pendientes': 0, 'rebotados': 0, 'invitados_recientes': []}


class RRPPSerializer(serializers.ModelSerializer):
    nombre = serializers.SerializerMethodField()
    username = serializers.CharField(source='usuario.username', read_only=True)
    asignaciones = AsignacionConEstadisticasSerializer(many=True, read_only=True)

    class Meta:
        model = RRPP
        fields = ['id', 'nombre', 'username', 'tipo_comision', 'valor_comision', 'asignaciones']

    def get_nombre(self, obj):
        return obj.usuario.get_full_name() or obj.usuario.username


class RRPPCreateSerializer(serializers.Serializer):
    nombre = serializers.CharField(max_length=150)
    apellido = serializers.CharField(max_length=150)
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, write_only=True)
    telefono = serializers.CharField(max_length=20, required=False, allow_blank=True)
    tipo_comision = serializers.ChoiceField(choices=RRPP.TIPO_COMISION)
    valor_comision = serializers.DecimalField(max_digits=10, decimal_places=2)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Este username ya existe.')
        return value

    def create(self, validated_data):
        organizador = self.context['organizador']
        with transaction.atomic():
            user = User.objects.create_user(
                username=validated_data['username'],
                password=validated_data['password'],
                first_name=validated_data['nombre'],
                last_name=validated_data['apellido'],
                telefono=validated_data.get('telefono', ''),
                rol='rrpp',
            )
            rrpp = RRPP.objects.create(
                usuario=user,
                organizador=organizador,
                tipo_comision=validated_data['tipo_comision'],
                valor_comision=validated_data['valor_comision'],
            )
        return rrpp
