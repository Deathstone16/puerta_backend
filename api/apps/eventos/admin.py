from django.contrib import admin

from .models import Evento


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'boliche', 'fecha', 'estado', 'precio_base', 'aforo_max']
    list_filter = ['estado', 'boliche', 'fecha']
    search_fields = ['nombre']
    readonly_fields = ['created_at', 'updated_at', 'motivo_cancelacion']
    date_hierarchy = 'fecha'
