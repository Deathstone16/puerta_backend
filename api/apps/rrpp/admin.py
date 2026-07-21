from django.contrib import admin

from .models import AsignacionRRPP, LinkRRPP, RRPP


class LinkRRPPInline(admin.TabularInline):
    model = LinkRRPP
    extra = 0
    readonly_fields = ['slug', 'activo']


@admin.register(RRPP)
class RRPPAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'boliche', 'tipo_comision', 'valor_comision']
    list_filter = ['boliche', 'tipo_comision']


@admin.register(AsignacionRRPP)
class AsignacionAdmin(admin.ModelAdmin):
    list_display = ['rrpp', 'evento', 'activa']
    list_filter = ['activa']
    inlines = [LinkRRPPInline]


@admin.register(LinkRRPP)
class LinkAdmin(admin.ModelAdmin):
    list_display = ['asignacion', 'tipo', 'slug', 'activo']
    list_filter = ['tipo', 'activo']
    readonly_fields = ['slug']
