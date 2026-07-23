"""
Add tipo_comision and valor_comision to AsignacionRRPP.
Make tipo_comision and valor_comision nullable on RRPP model.
"""
from django.db import migrations, models


def copiar_comision_a_asignaciones(apps, schema_editor):
    """Copy commission values from RRPP model to existing AsignacionRRPP records."""
    AsignacionRRPP = apps.get_model('rrpp', 'AsignacionRRPP')
    for asignacion in AsignacionRRPP.objects.select_related('rrpp').all():
        if asignacion.rrpp.tipo_comision and asignacion.rrpp.valor_comision is not None:
            asignacion.tipo_comision = asignacion.rrpp.tipo_comision
            asignacion.valor_comision = asignacion.rrpp.valor_comision
            asignacion.save(update_fields=['tipo_comision', 'valor_comision'])


class Migration(migrations.Migration):

    dependencies = [
        ('rrpp', '0002_rrpp_organizador_standalone'),
    ]

    operations = [
        # Add commission fields to AsignacionRRPP
        migrations.AddField(
            model_name='asignacionrrpp',
            name='tipo_comision',
            field=models.CharField(
                choices=[('fijo', 'Monto fijo por ingresado'), ('porcentaje', 'Porcentaje del recaudado')],
                default='fijo',
                help_text='Tipo de comisión para esta asignación específica',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='asignacionrrpp',
            name='valor_comision',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Valor de comisión para esta asignación específica',
                max_digits=10,
            ),
        ),
        # Make RRPP commission fields nullable
        migrations.AlterField(
            model_name='rrpp',
            name='tipo_comision',
            field=models.CharField(
                blank=True,
                choices=[('fijo', 'Monto fijo por ingresado'), ('porcentaje', 'Porcentaje del recaudado')],
                max_length=20,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name='rrpp',
            name='valor_comision',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=10,
                null=True,
            ),
        ),
        # Copy existing commission data from RRPP to AsignacionRRPP
        migrations.RunPython(copiar_comision_a_asignaciones, migrations.RunPython.noop),
    ]
