import uuid

from django.db import models


class Asistente(models.Model):
    TIPO_INGRESO = [
        ('web_anticipada', 'Compra Web'),
        ('lista_rrpp', 'Lista RRPP'),
        ('venta_general', 'Venta General'),
    ]
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('aprobado_guardia', 'Aprobado por Guardia'),
        ('rebotado_guardia', 'Rebotado por Guardia'),
        ('ingresado_final', 'Ingresado'),
    ]
    METODOS_PAGO = [
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia'),
        ('ya_pago_web', 'Ya pagó por web'),
    ]

    evento = models.ForeignKey(
        'eventos.Evento', on_delete=models.PROTECT, related_name='asistentes',
    )
    link_rrpp = models.ForeignKey(
        'rrpp.LinkRRPP', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='asistentes',
    )
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    dni = models.CharField(max_length=20)
    instagram = models.CharField(
        max_length=100, blank=True, default='',
        help_text='Username de Instagram del asistente',
    )
    tipo_ingreso = models.CharField(max_length=20, choices=TIPO_INGRESO)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    metodo_pago = models.CharField(
        max_length=20, choices=METODOS_PAGO, null=True, blank=True,
    )
    monto_pagado = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
    )

    wallet_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    mp_payment_id = models.CharField(max_length=100, null=True, blank=True, unique=True)
    mp_fee_norware = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
    )
    motivo_rechazo = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    aprobado_at = models.DateTimeField(null=True, blank=True)
    ingresado_at = models.DateTimeField(null=True, blank=True)
    rebotado_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Asistente'
        verbose_name_plural = 'Asistentes'
        unique_together = ('evento', 'dni')

    def __str__(self):
        return f"{self.nombre} {self.apellido} — DNI {self.dni} ({self.estado})"
