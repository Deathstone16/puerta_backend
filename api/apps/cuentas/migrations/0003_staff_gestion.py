"""
Add organizador field to Usuario and create AsignacionStaff model.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cuentas', '0002_usuario_add_rol'),
        ('eventos', '0003_evento_organizador_standalone'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='organizador',
            field=models.ForeignKey(
                blank=True,
                help_text='Dueño que creó este usuario (solo para staff: guardia/cajera)',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='staff_creado',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.CreateModel(
            name='AsignacionStaff',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rol', models.CharField(choices=[('guardia', 'Guardia'), ('cajera', 'Cajera')], max_length=20)),
                ('activa', models.BooleanField(default=True)),
                ('usuario', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='asignaciones_staff',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('evento', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='staff_asignado',
                    to='eventos.evento',
                )),
            ],
            options={
                'verbose_name': 'Asignación de Staff',
                'verbose_name_plural': 'Asignaciones de Staff',
                'unique_together': {('usuario', 'evento')},
            },
        ),
    ]
