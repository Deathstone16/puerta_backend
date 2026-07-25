# Generated manually — aprobado_rrpp field for RRPP approval tracking

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('puerta', '0002_asistente_instagram'),
    ]

    operations = [
        migrations.AddField(
            model_name='asistente',
            name='aprobado_rrpp',
            field=models.BooleanField(default=False),
        ),
    ]