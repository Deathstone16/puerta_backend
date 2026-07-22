from django.contrib import admin
from django.utils.html import format_html

from .models import Boliche


@admin.register(Boliche)
class BolicheAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'dueno', 'mp_status_badge', 'created_at']
    list_filter = ['created_at']
    search_fields = ['nombre', 'dueno__username', 'dueno__first_name']
    readonly_fields = ['created_at', 'mp_connected_at', 'mp_user_id', 'mp_status_badge']
    list_per_page = 20

    fieldsets = (
        ('Datos del boliche', {
            'fields': ('nombre', 'direccion', 'dueno'),
        }),
        ('Mercado Pago — Conexión OAuth', {
            'fields': ('mp_status_badge', 'mp_user_id', 'mp_connected_at'),
            'description': 'El dueño conecta su cuenta via el botón "Conectar Mercado Pago" en el frontend.',
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Estado MP')
    def mp_status_badge(self, obj):
        if obj.mp_connected:
            return format_html(
                '<span style="background:#22C55E; color:white; padding:3px 8px; '
                'border-radius:4px; font-size:11px;">✓ CONECTADO</span>'
            )
        return format_html(
            '<span style="background:#E23B5A; color:white; padding:3px 8px; '
            'border-radius:4px; font-size:11px;">✗ SIN CONECTAR</span>'
        )
