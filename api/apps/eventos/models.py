from django.db import models


class Evento(models.Model):
    ESTADOS = [('activo', 'Activo'), ('cancelado', 'Cancelado')]

    boliche = models.ForeignKey(
        'boliches.Boliche',
        on_delete=models.PROTECT,
        related_name='eventos',
    )
    nombre = models.CharField(max_length=200)
    fecha = models.DateTimeField()
    aforo_max = models.PositiveIntegerField()
    color_pulsera = models.CharField(max_length=50)
    precio_base = models.DecimalField(max_digits=10, decimal_places=2)
    line_up = models.JSONField(default=list, blank=True)
    habilitar_lista = models.BooleanField(
        default=True,
        help_text='Indica si el evento permite listas RRPP o solo venta anticipada web',
    )
    estado = models.CharField(max_length=20, choices=ESTADOS, default='activo')
    motivo_cancelacion = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Evento'
        verbose_name_plural = 'Eventos'
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.nombre} — {self.fecha.strftime('%d/%m/%Y')} ({self.estado})"
