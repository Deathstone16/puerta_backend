from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ['username', 'rol_badge', 'first_name', 'last_name', 'telefono', 'is_active', 'date_joined']
    list_filter = ['rol', 'is_staff', 'is_superuser', 'is_active']
    search_fields = ['username', 'first_name', 'last_name', 'email', 'telefono']
    list_per_page = 25
    ordering = ['-date_joined']

    fieldsets = UserAdmin.fieldsets + (
        ('Norware — Rol y Contacto', {
            'fields': ('rol', 'telefono'),
            'classes': ('wide',),
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Norware — Rol y Contacto', {
            'fields': ('rol', 'telefono'),
            'classes': ('wide',),
        }),
    )

    @admin.display(description='Rol', ordering='rol')
    def rol_badge(self, obj):
        colores = {
            'superadmin': '#E23B5A',
            'dueno': '#8B5CF6',
            'rrpp': '#22D3EE',
            'guardia': '#F97316',
            'cajera': '#22C55E',
        }
        color = colores.get(obj.rol, '#8A87A3')
        return format_html(
            '<span style="background:{}; color:white; padding:3px 8px; '
            'border-radius:4px; font-size:11px; font-weight:bold;">{}</span>',
            color, obj.get_rol_display().upper(),
        )
