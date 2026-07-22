from django.contrib import admin
from django.utils.html import format_html

from .models import Evento
from .utils import calcular_precio_publicado


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = [
        'nombre', 'boliche', 'fecha', 'estado_badge', 'pulsera_badge',
        'precio_publicado_display', 'aforo_max', 'habilitar_lista',
    ]
    list_filter = ['estado', 'boliche', 'habilitar_lista', 'fecha']
    search_fields = ['nombre', 'boliche__nombre']
    readonly_fields = [
        'created_at', 'updated_at', 'motivo_cancelacion',
        'precio_publicado_display', 'desglose_display',
    ]
    date_hierarchy = 'fecha'
    list_per_page = 20
    ordering = ['-fecha']

    fieldsets = (
        ('Evento', {
            'fields': ('boliche', 'nombre', 'fecha', 'estado'),
        }),
        ('Configuración', {
            'fields': ('aforo_max', 'color_pulsera', 'habilitar_lista', 'line_up'),
        }),
        ('Precios', {
            'fields': ('precio_base', 'precio_publicado_display', 'desglose_display'),
            'description': 'El precio publicado se calcula automáticamente sumando fees de MP y Norware.',
        }),
        ('Cancelación', {
            'fields': ('motivo_cancelacion',),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Estado')
    def estado_badge(self, obj):
        if obj.estado == 'activo':
            return format_html(
                '<span style="background:#22C55E; color:white; padding:3px 8px; '
                'border-radius:4px; font-size:11px;">ACTIVO</span>'
            )
        return format_html(
            '<span style="background:#E23B5A; color:white; padding:3px 8px; '
            'border-radius:4px; font-size:11px;">CANCELADO</span>'
        )

    @admin.display(description='Pulsera')
    def pulsera_badge(self, obj):
        return format_html(
            '<span style="background:#1a1a2e; border:2px solid #8B5CF6; color:#EDEBF5; '
            'padding:2px 8px; border-radius:0; font-size:11px; font-weight:bold;">'
            '◆ {}</span>',
            obj.color_pulsera.upper(),
        )

    @admin.display(description='Precio publicado')
    def precio_publicado_display(self, obj):
        try:
            result = calcular_precio_publicado(obj.precio_base)
            return format_html(
                '<strong style="color:#22D3EE; font-family:monospace; font-size:14px;">'
                '${:,.0f}</strong>',
                result['precio_publicado'],
            )
        except Exception:
            return '—'

    @admin.display(description='Desglose de fees')
    def desglose_display(self, obj):
        try:
            r = calcular_precio_publicado(obj.precio_base)
            return format_html(
                'Base: ${:,.0f} + MP: ${:,.0f} + Norware: ${:,.0f} = <strong>${:,.0f}</strong>',
                r['precio_base'], r['fee_mp'], r['fee_norware'], r['precio_publicado'],
            )
        except Exception:
            return '—'
