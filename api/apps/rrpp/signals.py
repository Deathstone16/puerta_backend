from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import AsignacionRRPP, LinkRRPP


@receiver(post_save, sender=AsignacionRRPP)
def crear_links_rrpp(sender, instance, created, **kwargs):
    """
    Al crear una nueva AsignacionRRPP, genera automáticamente
    2 LinkRRPP: uno de tipo 'lista' y otro de tipo 'venta_web'.
    """
    if not created:
        return

    LinkRRPP.objects.bulk_create([
        LinkRRPP(asignacion=instance, tipo='lista'),
        LinkRRPP(asignacion=instance, tipo='venta_web'),
    ])
