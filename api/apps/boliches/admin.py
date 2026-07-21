from django.contrib import admin

from .models import Boliche


@admin.register(Boliche)
class BolicheAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'dueno', 'mp_connected', 'mp_user_id', 'created_at']
    list_filter = ['created_at']
    search_fields = ['nombre', 'dueno__username']
    readonly_fields = ['created_at', 'mp_connected_at', 'mp_user_id']
    fieldsets = (
        (None, {'fields': ('nombre', 'direccion', 'dueno')}),
        ('Mercado Pago', {
            'fields': ('mp_user_id', 'mp_connected_at'),
            'description': 'Datos de la conexión OAuth con Mercado Pago.',
        }),
    )
