from django.contrib import admin
from django.utils.html import format_html

from .models import Asistente


@admin.register(Asistente)
class AsistenteAdmin(admin.ModelAdmin):
    list_display = [
        'nombre_completo', 'dni', 'instagram_display', 'evento',
        'tipo_ingreso_badge', 'estado_badge', 'metodo_pago', 'created_at',
    ]
    list_filter = ['estado', 'tipo_ingreso', 'metodo_pago', 'evento']
    search_fields = ['nombre', 'apellido', 'dni', 'instagram']
    readonly_fields = [
        'wallet_token', 'mp_payment_id', 'mp_fee_norware',
        'created_at', 'aprobado_at', 'ingresado_at', 'rebotado_at',
    ]
    list_per_page = 50
    ordering = ['-created_at']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Persona', {
            'fields': ('nombre', 'apellido', 'dni', 'instagram'),
        }),
        ('Evento y RRPP', {
            'fields': ('evento', 'link_rrpp', 'tipo_ingreso'),
        }),
        ('Estado y pago', {
            'fields': ('estado', 'metodo_pago', 'monto_pagado', 'motivo_rechazo'),
        }),
        ('Ticket / QR', {
            'fields': ('wallet_token',),
        }),
        ('Mercado Pago', {
            'fields': ('mp_payment_id', 'mp_fee_norware'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'aprobado_at', 'ingresado_at', 'rebotado_at'),
            'classes': ('collapse',),
        }),
    )

    actions = ['marcar_como_aprobado', 'marcar_como_rebotado']

    @admin.display(description='Nombre', ordering='apellido')
    def nombre_completo(self, obj):
        return f"{obj.nombre} {obj.apellido}"

    @admin.display(description='Instagram')
    def instagram_display(self, obj):
        if obj.instagram:
            return format_html(
                '<a href="https://instagram.com/{}" target="_blank" '
                'style="color:#E1306C;">@{}</a>',
                obj.instagram.lstrip('@'), obj.instagram.lstrip('@'),
            )
        return '—'

    @admin.display(description='Tipo')
    def tipo_ingreso_badge(self, obj):
        colores = {
            'web_anticipada': '#8B5CF6',
            'lista_rrpp': '#22D3EE',
            'venta_general': '#F97316',
        }
        color = colores.get(obj.tipo_ingreso, '#8A87A3')
        label = obj.get_tipo_ingreso_display()
        return format_html(
            '<span style="background:{}; color:white; padding:2px 6px; '
            'border-radius:4px; font-size:10px;">{}</span>',
            color, label,
        )

    @admin.display(description='Estado')
    def estado_badge(self, obj):
        colores = {
            'pendiente': '#8A87A3',
            'aprobado_guardia': '#8B5CF6',
            'rebotado_guardia': '#E23B5A',
            'ingresado_final': '#22C55E',
        }
        color = colores.get(obj.estado, '#8A87A3')
        label = obj.get_estado_display()
        return format_html(
            '<span style="background:{}; color:white; padding:2px 6px; '
            'border-radius:4px; font-size:10px; font-weight:bold;">{}</span>',
            color, label.upper(),
        )

    @admin.action(description='✓ Marcar como aprobado por guardia')
    def marcar_como_aprobado(self, request, queryset):
        from django.utils import timezone
        updated = queryset.filter(estado='pendiente').update(
            estado='aprobado_guardia', aprobado_at=timezone.now(),
        )
        self.message_user(request, f'{updated} asistente(s) aprobados.')

    @admin.action(description='✗ Marcar como rebotado')
    def marcar_como_rebotado(self, request, queryset):
        from django.utils import timezone
        updated = queryset.filter(estado='pendiente').update(
            estado='rebotado_guardia', rebotado_at=timezone.now(),
            motivo_rechazo='Rebotado desde admin',
        )
        self.message_user(request, f'{updated} asistente(s) rebotados.')
