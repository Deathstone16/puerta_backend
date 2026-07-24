from django.utils import timezone
from rest_framework import serializers

from .models import Evento
from .utils import calcular_precio_publicado

# Meses abreviados en español para `fechaCorta` (ej: "24 jul").
_MESES_ABREV = [
    'ene', 'feb', 'mar', 'abr', 'may', 'jun',
    'jul', 'ago', 'sep', 'oct', 'nov', 'dic',
]


class EventoListSerializer(serializers.ModelSerializer):
    precio_publicado = serializers.SerializerMethodField()
    organizador_nombre = serializers.SerializerMethodField()
    # Campos derivados que consume el frontend público (EventCard, detalle, etc.)
    slug = serializers.SerializerMethodField()
    club = serializers.SerializerMethodField()
    ciudad = serializers.SerializerMethodField()
    genero = serializers.SerializerMethodField()
    imagen = serializers.SerializerMethodField()
    fechaCorta = serializers.SerializerMethodField()
    horario = serializers.SerializerMethodField()
    lineup = serializers.SerializerMethodField()

    class Meta:
        model = Evento
        fields = [
            'id', 'nombre', 'fecha', 'color_pulsera',
            'precio_base', 'precio_publicado', 'aforo_max',
            'estado', 'habilitar_lista', 'organizador_nombre',
            'slug', 'club', 'ciudad', 'genero', 'imagen',
            'fechaCorta', 'horario', 'lineup',
        ]
        read_only_fields = ['id', 'estado', 'organizador_nombre']

    def get_precio_publicado(self, obj):
        return calcular_precio_publicado(obj.precio_base)['precio_publicado']

    def get_organizador_nombre(self, obj):
        if obj.organizador:
            nombre = f"{obj.organizador.first_name} {obj.organizador.last_name}".strip()
            return nombre if nombre else obj.organizador.username
        return None

    def get_slug(self, obj):
        return str(obj.id)

    def get_club(self, obj):
        return obj.boliche.nombre if obj.boliche_id else None

    def get_ciudad(self, obj):
        # `direccion` es texto libre; best-effort: último segmento tras una coma.
        if not obj.boliche_id or not obj.boliche.direccion:
            return None
        partes = [p.strip() for p in obj.boliche.direccion.split(',') if p.strip()]
        return partes[-1] if len(partes) > 1 else obj.boliche.direccion.strip()

    def get_genero(self, obj):
        return 'Techno'

    def get_imagen(self, obj):
        return None

    def get_fechaCorta(self, obj):
        if not obj.fecha:
            return None
        local = timezone.localtime(obj.fecha)
        return f"{local.day:02d} {_MESES_ABREV[local.month - 1]}"

    def get_horario(self, obj):
        if not obj.fecha:
            return None
        return timezone.localtime(obj.fecha).strftime('%H:%M')

    def get_lineup(self, obj):
        return obj.line_up


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
