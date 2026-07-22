from django.contrib import admin
from django.utils.html import format_html

from .models import AsignacionRRPP, LinkRRPP, RRPP


class LinkRRPPInline(admin.TabularInline):
    model = LinkRRPP
    extra = 0
    readonly_fields = ['tipo', 'slug', 'activo', 'url_display']
    fields = ['tipo', 'slug', 'activo', 'url_display']

    @admin.display(description='URL pública')
    def url_display(self, obj):
        if obj.tipo == 'lista':
            url = f"/lista/{obj.slug}/"
        else:
            url = f"/venta/{obj.slug}/"
        return format_html('<code style="color:#22D3EE;">{}</code>', url)


class AsignacionInline(admin.TabularInline):
    model = AsignacionRRPP
    extra = 0
    readonly_fields = ['evento', 'activa']
    fields = ['evento', 'activa']


@admin.register(RRPP)
class RRPPAdmin(admin.ModelAdmin):
    list_display = ['nombre_display', 'boliche', 'comision_display', 'eventos_count']
    list_filter = ['boliche', 'tipo_comision']
    search_fields = ['usuario__username', 'usuario__first_name', 'usuario__last_name']
    inlines = [AsignacionInline]
    list_per_page = 25

    @admin.display(description='RRPP', ordering='usuario__last_name')
    def nombre_display(self, obj):
        nombre = obj.usuario.get_full_name() or obj.usuario.username
        return format_html(
            '<strong>{}</strong> <span style="color:#8A87A3;">(@{})</span>',
            nombre, obj.usuario.username,
        )

    @admin.display(description='Comisión')
    def comision_display(self, obj):
        if obj.tipo_comision == 'fijo':
            return format_html(
                '<span style="color:#22D3EE; font-family:monospace;">${:,.0f}/ingresado</span>',
                obj.valor_comision,
            )
        return format_html(
            '<span style="color:#22D3EE; font-family:monospace;">{}% del recaudado</span>',
            obj.valor_comision,
        )

    @admin.display(description='Eventos')
    def eventos_count(self, obj):
        count = obj.asignaciones.filter(activa=True).count()
        return format_html(
            '<span style="background:#141220; color:#EDEBF5; padding:2px 8px; '
            'border-radius:4px;">{}</span>',
            count,
        )


@admin.register(AsignacionRRPP)
class AsignacionAdmin(admin.ModelAdmin):
    list_display = ['rrpp', 'evento', 'activa_badge', 'links_count']
    list_filter = ['activa', 'evento']
    inlines = [LinkRRPPInline]
    list_per_page = 25

    @admin.display(description='Estado')
    def activa_badge(self, obj):
        if obj.activa:
            return format_html(
                '<span style="color:#22C55E; font-weight:bold;">● Activa</span>'
            )
        return format_html(
            '<span style="color:#E23B5A;">● Inactiva</span>'
        )

    @admin.display(description='Links')
    def links_count(self, obj):
        return obj.links.count()


@admin.register(LinkRRPP)
class LinkAdmin(admin.ModelAdmin):
    list_display = ['asignacion', 'tipo_badge', 'slug', 'activo_badge']
    list_filter = ['tipo', 'activo']
    readonly_fields = ['slug']
    list_per_page = 25

    @admin.display(description='Tipo')
    def tipo_badge(self, obj):
        color = '#8B5CF6' if obj.tipo == 'lista' else '#22D3EE'
        return format_html(
            '<span style="background:{}; color:white; padding:2px 6px; '
            'border-radius:4px; font-size:10px;">{}</span>',
            color, obj.get_tipo_display().upper(),
        )

    @admin.display(description='Estado')
    def activo_badge(self, obj):
        if obj.activo:
            return format_html('<span style="color:#22C55E;">● Activo</span>')
        return format_html('<span style="color:#E23B5A;">● Inactivo</span>')
