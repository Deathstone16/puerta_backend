"""
Migración: RRPP standalone (sin dependencia obligatoria de Boliche).
- Agrega campo 'organizador' (FK a Usuario)
- Hace 'boliche' opcional (null=True, blank=True)
- Pobla organizador desde boliche.dueno para datos existentes
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def populate_organizador(apps, schema_editor):
    """Para RRPPs existentes, copia boliche.dueno → organizador."""
    RRPP = apps.get_model('rrpp', 'RRPP')
    for rrpp in RRPP.objects.select_related('boliche').filter(organizador__isnull=True):
        if rrpp.boliche_id:
            rrpp.organizador = rrpp.boliche.dueno
            rrpp.save(update_fields=['organizador'])


class Migration(migrations.Migration):

    dependencies = [
        ('rrpp', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Agregar organizador como nullable primero
        migrations.AddField(
            model_name='rrpp',
            name='organizador',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='rrpps',
                to=settings.AUTH_USER_MODEL,
                help_text='Dueño/organizador que creó este RRPP',
            ),
        ),
        # 2. Poblar organizador desde boliche.dueno
        migrations.RunPython(populate_organizador, migrations.RunPython.noop),
        # 3. Hacer organizador NOT NULL
        migrations.AlterField(
            model_name='rrpp',
            name='organizador',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='rrpps',
                to=settings.AUTH_USER_MODEL,
                help_text='Dueño/organizador que creó este RRPP',
            ),
        ),
        # 4. Hacer boliche opcional
        migrations.AlterField(
            model_name='rrpp',
            name='boliche',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='rrpps',
                to='boliches.boliche',
                help_text='Boliche asociado (opcional para esta versión)',
            ),
        ),
    ]
