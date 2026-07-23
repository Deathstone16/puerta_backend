from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    ROLES = [
        ('superadmin', 'Super Admin'),
        ('dueno', 'Dueño'),
        ('rrpp', 'RRPP'),
        ('guardia', 'Guardia'),
        ('cajera', 'Cajera'),
    ]

    rol = models.CharField(
        max_length=20,
        choices=ROLES,
        help_text='Rol del usuario en la plataforma',
    )
    telefono = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text='Número de teléfono de contacto',
    )
    organizador = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff_creado',
        help_text='Dueño que creó este usuario (solo para staff: guardia/cajera)',
    )

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return f"{self.username} ({self.get_rol_display()})"


class AsignacionStaff(models.Model):
    """Asignación de un guardia o cajera a un evento específico."""
    ROL_CHOICES = [('guardia', 'Guardia'), ('cajera', 'Cajera')]

    usuario = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, related_name='asignaciones_staff',
    )
    evento = models.ForeignKey(
        'eventos.Evento', on_delete=models.CASCADE, related_name='staff_asignado',
    )
    rol = models.CharField(max_length=20, choices=ROL_CHOICES)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Asignación de Staff'
        verbose_name_plural = 'Asignaciones de Staff'
        unique_together = ('usuario', 'evento')

    def __str__(self):
        return f"{self.usuario.get_full_name() or self.usuario.username} ({self.rol}) → {self.evento.nombre}"
