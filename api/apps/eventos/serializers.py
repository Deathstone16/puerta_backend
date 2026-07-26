from rest_framework import serializers

from .models import Evento
from .utils import calcular_precio_publicado


class EventoListSerializer(serializers.ModelSerializer):
    precio_publicado = serializers.SerializerMethodField()
    organizador_nombre = serializers.SerializerMethodField()
    fecha_corta = serializers.SerializerMethodField()
    club = serializers.SerializerMethodField()
    ciudad = serializers.SerializerMethodField()
    horario = serializers.SerializerMethodField()
    imagen = serializers.SerializerMethodField()
    genero = serializers.SerializerMethodField()
    descripcion = serializers.SerializerMethodField()

    class Meta:
        model = Evento
        fields = [
            'id', 'nombre', 'fecha', 'fecha_corta', 'color_pulsera',
            'precio_base', 'precio_publicado', 'aforo_max',
            'estado', 'habilitar_lista', 'organizador_nombre',
            'club', 'ciudad', 'horario', 'line_up', 'imagen',
            'genero', 'descripcion',
        ]
        read_only_fields = ['id', 'estado', 'organizador_nombre']

    def get_precio_publicado(self, obj):
        return calcular_precio_publicado(obj.precio_base)['precio_publicado']

    def get_organizador_nombre(self, obj):
        if obj.organizador:
            nombre = f"{obj.organizador.first_name} {obj.organizador.last_name}".strip()
            return nombre if nombre else obj.organizador.username
        return None

    def get_fecha_corta(self, obj):
        return obj.fecha.strftime('%a %d %b').upper() if obj.fecha else None

    def get_club(self, obj):
        return obj.boliche.nombre if obj.boliche else None

    def get_ciudad(self, obj):
        if obj.boliche:
            return obj.boliche.ciudad or None
        return None

    def get_horario(self, obj):
        return obj.fecha.strftime('%H:%M') if obj.fecha else None

    def get_imagen(self, obj):
        return obj.imagen or None

    def get_genero(self, obj):
        return obj.genero or None

    def get_descripcion(self, obj):
        return obj.descripcion or None


class EventoDetailSerializer(EventoListSerializer):
    desglose_precio = serializers.SerializerMethodField()
    lista_slug = serializers.SerializerMethodField()

    class Meta(EventoListSerializer.Meta):
        fields = EventoListSerializer.Meta.fields + [
            'desglose_precio', 'lista_slug',
            'motivo_cancelacion', 'created_at', 'updated_at',
        ]
        read_only_fields = EventoListSerializer.Meta.read_only_fields + [
            'motivo_cancelacion', 'created_at', 'updated_at',
        ]

    def get_desglose_precio(self, obj):
        return calcular_precio_publicado(obj.precio_base)

    def get_lista_slug(self, obj):
        """Retorna el slug del primer link de lista activo para este evento, o None."""
        try:
            from apps.rrpp.models import LinkRRPP
            link = LinkRRPP.objects.filter(
                asignacion__evento=obj, tipo='lista', activo=True,
            ).first()
            return str(link.slug) if link else None
        except Exception:
            return None
