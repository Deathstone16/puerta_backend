from django.conf import settings
from django.db import models


class Boliche(models.Model):
    nombre = models.CharField(max_length=200)
    direccion = models.TextField()
    dueno = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='boliches',
    )
    # --- Mercado Pago OAuth Marketplace ---
    mp_access_token = models.TextField(
        blank=True, null=True,
        help_text='Access token del vendedor obtenido via OAuth MP',
    )
    mp_refresh_token = models.TextField(
        blank=True, null=True,
        help_text='Refresh token para renovar el access token',
    )
    mp_user_id = models.CharField(
        max_length=100, blank=True, null=True,
        help_text='ID del vendedor en MP (collector_id real)',
    )
    mp_connected_at = models.DateTimeField(
        blank=True, null=True,
        help_text='Fecha en que el dueño conectó su cuenta MP',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Boliche'
        verbose_name_plural = 'Boliches'

    @property
    def mp_connected(self):
        """True si el dueño ya conectó su cuenta de Mercado Pago."""
        return bool(self.mp_access_token and self.mp_user_id)

    def __str__(self):
        return f"{self.nombre} ({self.dueno.username})"
