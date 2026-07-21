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

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return f"{self.username} ({self.get_rol_display()})"
