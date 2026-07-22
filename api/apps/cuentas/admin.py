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

    # Formulario de edición
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Datos personales', {'fields': ('first_name', 'last_name', 'email', 'telefono')}),
        ('Norware', {
            'fields': ('rol',),
            'description': 'Seleccioná el rol que va a tener en la plataforma.',
        }),
        ('Permisos Django', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',),
        }),
        ('Fechas', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',),
        }),
    )

    # Formulario de CREACIÓN — todo lo necesario en una sola pantalla
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2'),
        }),
        ('Datos personales', {
            'classes': ('wide',),
            'fields': ('first_name', 'last_name', 'email', 'telefono'),
        }),
        ('Rol en Norware', {
            'classes': ('wide',),
            'fields': ('rol',),
            'description': (
                'Para crear un DUEÑO de boliche, elegí "Dueño". '
                'Después el dueño puede crear sus propios RRPP desde la plataforma.'
            ),
        }),
    )

    actions = ['activar_usuarios', 'desactivar_usuarios']

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

    @admin.action(description='✓ Activar usuarios seleccionados')
    def activar_usuarios(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} usuario(s) activados.')

    @admin.action(description='✗ Desactivar usuarios seleccionados')
    def desactivar_usuarios(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} usuario(s) desactivados.')
