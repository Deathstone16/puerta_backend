from django.db import migrations, models


def asignar_rol_default(apps, schema_editor):
    Usuario = apps.get_model('cuentas', 'Usuario')
    for usuario in Usuario.objects.all():
        if not usuario.rol:
            if usuario.is_superuser:
                usuario.rol = 'superadmin'
            else:
                usuario.rol = 'dueno'
            usuario.save()


class Migration(migrations.Migration):

    dependencies = [
        ('cuentas', '0001_initial'),
    ]

    operations = [
        # Paso 1: agregar rol como nullable para que la migración no falle con rows existentes
        migrations.AddField(
            model_name='usuario',
            name='rol',
            field=models.CharField(
                blank=True,
                choices=[
                    ('superadmin', 'Super Admin'),
                    ('dueno', 'Dueño'),
                    ('rrpp', 'RRPP'),
                    ('guardia', 'Guardia'),
                    ('cajera', 'Cajera'),
                ],
                default='',
                help_text='Rol del usuario en la plataforma',
                max_length=20,
            ),
            preserve_default=False,
        ),
        # Paso 2: asignar rol a usuarios existentes
        migrations.RunPython(asignar_rol_default, migrations.RunPython.noop),
        # Paso 3: hacer rol obligatorio (no blank)
        migrations.AlterField(
            model_name='usuario',
            name='rol',
            field=models.CharField(
                choices=[
                    ('superadmin', 'Super Admin'),
                    ('dueno', 'Dueño'),
                    ('rrpp', 'RRPP'),
                    ('guardia', 'Guardia'),
                    ('cajera', 'Cajera'),
                ],
                help_text='Rol del usuario en la plataforma',
                max_length=20,
            ),
        ),
    ]
