import uuid

from django.conf import settings
from django.db import models


class RRPP(models.Model):
    TIPO_COMISION = [
        ('fijo', 'Monto fijo por ingresado'),
        ('porcentaje', 'Porcentaje del recaudado'),
    ]

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='perfil_rrpp',
    )
    organizador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='rrpps',
        help_text='Dueño/organizador que creó este RRPP',
    )
    boliche = models.ForeignKey(
        'boliches.Boliche',
        on_delete=models.PROTECT,
        related_name='rrpps',
        blank=True,
        null=True,
        help_text='Boliche asociado (opcional para esta versión)',
    )
    tipo_comision = models.CharField(max_length=20, choices=TIPO_COMISION)
    valor_comision = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = 'RRPP'
        verbose_name_plural = 'RRPPs'

    def __str__(self):
        nombre = self.usuario.get_full_name() or self.usuario.username
        org = self.organizador.get_full_name() or self.organizador.username
        return f"{nombre} — {org}"


class AsignacionRRPP(models.Model):
    rrpp = models.ForeignKey(RRPP, on_delete=models.CASCADE, related_name='asignaciones')
    evento = models.ForeignKey(
        'eventos.Evento', on_delete=models.CASCADE, related_name='asignaciones_rrpp',
    )
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Asignación RRPP'
        verbose_name_plural = 'Asignaciones RRPP'
        unique_together = ('rrpp', 'evento')

    def __str__(self):
        return f"{self.rrpp} → {self.evento.nombre}"


class LinkRRPP(models.Model):
    TIPOS = [('lista', 'Lista'), ('venta_web', 'Venta Web')]

    asignacion = models.ForeignKey(
        AsignacionRRPP, on_delete=models.CASCADE, related_name='links',
    )
    tipo = models.CharField(max_length=20, choices=TIPOS)
    slug = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Link RRPP'
        verbose_name_plural = 'Links RRPP'

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.slug} ({'activo' if self.activo else 'inactivo'})"
