from django.contrib import admin

from .models import Asistente


@admin.register(Asistente)
class AsistenteAdmin(admin.ModelAdmin):
    list_display = [
        'nombre', 'apellido', 'dni', 'evento', 'tipo_ingreso',
        'estado', 'metodo_pago', 'created_at',
    ]
    list_filter = ['estado', 'tipo_ingreso', 'metodo_pago', 'evento']
    search_fields = ['nombre', 'apellido', 'dni']
    readonly_fields = [
        'wallet_token', 'mp_payment_id', 'created_at',
        'aprobado_at', 'ingresado_at', 'rebotado_at',
    ]
