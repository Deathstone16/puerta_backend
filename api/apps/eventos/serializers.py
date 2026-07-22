from rest_framework import serializers

from .models import Evento
from .utils import calcular_precio_publicado


class EventoListSerializer(serializers.ModelSerializer):
    precio_publicado = serializers.SerializerMethodField()
    organizador_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Evento
        fields = [
            'id', 'nombre', 'fecha', 'color_pulsera',
            'precio_base', 'precio_publicado', 'aforo_max',
            'estado', 'habilitar_lista', 'organizador_nombre',
        ]
        read_only_fields = ['id', 'estado', 'organizador_nombre']

    def get_precio_publicado(self, obj):
        return calcular_precio_publicado(obj.precio_base)['precio_publicado']

    def get_organizador_nombre(self, obj):
        if obj.organizador:
            nombre = f"{obj.organizador.first_name} {obj.organizador.last_name}".strip()
            return nombre if nombre else obj.organizador.username
        return None


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
