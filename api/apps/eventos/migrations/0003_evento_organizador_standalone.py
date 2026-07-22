"""
Migración: Evento standalone (sin dependencia obligatoria de Boliche).
- Agrega campo 'organizador' (FK a Usuario)
- Hace 'boliche' opcional (null=True, blank=True)
- Hace 'color_pulsera' con default y blank=True
- Pobla organizador desde boliche.dueno para datos existentes
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def populate_organizador(apps, schema_editor):
    """Para eventos existentes, copia boliche.dueno → organizador."""
    Evento = apps.get_model('eventos', 'Evento')
    for evento in Evento.objects.select_related('boliche').filter(organizador__isnull=True):
        if evento.boliche_id:
            evento.organizador = evento.boliche.dueno
            evento.save(update_fields=['organizador'])


class Migration(migrations.Migration):

    dependencies = [
        ('eventos', '0002_evento_habilitar_lista'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Agregar organizador como nullable primero
        migrations.AddField(
            model_name='evento',
            name='organizador',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='eventos',
                to=settings.AUTH_USER_MODEL,
                help_text='Usuario dueño/organizador del evento',
            ),
        ),
        # 2. Poblar organizador desde boliche.dueno
        migrations.RunPython(populate_organizador, migrations.RunPython.noop),
        # 3. Hacer organizador NOT NULL
        migrations.AlterField(
            model_name='evento',
            name='organizador',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='eventos',
                to=settings.AUTH_USER_MODEL,
                help_text='Usuario dueño/organizador del evento',
            ),
        ),
        # 4. Hacer boliche opcional
        migrations.AlterField(
            model_name='evento',
            name='boliche',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='eventos',
                to='boliches.boliche',
                help_text='Boliche asociado (opcional para esta versión)',
            ),
        ),
        # 5. color_pulsera con default y blank
        migrations.AlterField(
            model_name='evento',
            name='color_pulsera',
            field=models.CharField(blank=True, default='amarilla', max_length=50),
        ),
    ]
