from rest_framework import serializers

from apps.boliches.models import Boliche

from .models import Evento
from .utils import calcular_precio_publicado


class BolicheResumenSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    nombre = serializers.CharField(read_only=True)
    direccion = serializers.CharField(read_only=True)


class EventoListSerializer(serializers.ModelSerializer):
    precio_publicado = serializers.SerializerMethodField()
    boliche = BolicheResumenSerializer(read_only=True)
    boliche_id = serializers.PrimaryKeyRelatedField(
        source='boliche',
        queryset=Boliche.objects.all(),
        write_only=True,
    )

    class Meta:
        model = Evento
        fields = [
            'id', 'nombre', 'fecha', 'color_pulsera',
            'precio_base', 'precio_publicado', 'aforo_max',
            'estado', 'habilitar_lista', 'boliche', 'boliche_id',
        ]
        read_only_fields = ['id', 'estado']

    def get_precio_publicado(self, obj):
        return calcular_precio_publicado(obj.precio_base)['precio_publicado']


class EventoDetailSerializer(EventoListSerializer):
    desglose_precio = serializers.SerializerMethodField()

    class Meta(EventoListSerializer.Meta):
        fields = EventoListSerializer.Meta.fields + [
            'line_up', 'desglose_precio',
            'motivo_cancelacion', 'created_at', 'updated_at',
        ]
        read_only_fields = EventoListSerializer.Meta.read_only_fields + [
            'motivo_cancelacion', 'created_at', 'updated_at',
        ]

    def get_desglose_precio(self, obj):
        return calcular_precio_publicado(obj.precio_base)
