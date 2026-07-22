"""
Management command para crear el superuser automáticamente en deploy.
Lee ADMIN_USERNAME y ADMIN_PASSWORD de las variables de entorno.
Si el usuario ya existe, no hace nada (idempotente).

Uso:
    python manage.py crear_superuser

En el Build Command de Render agregar al final:
    && python manage.py crear_superuser
"""
import os

from django.core.management.base import BaseCommand

from apps.cuentas.models import Usuario


class Command(BaseCommand):
    help = 'Crea el superuser si no existe (lee credenciales de env vars)'

    def handle(self, *args, **options):
        username = os.environ.get('ADMIN_USERNAME', 'admin')
        password = os.environ.get('ADMIN_PASSWORD', '')
        email = os.environ.get('ADMIN_EMAIL', 'admin@norware.com')

        if not password:
            self.stdout.write(self.style.WARNING(
                'ADMIN_PASSWORD no está definido. Saltando creación de superuser.'
            ))
            return

        if Usuario.objects.filter(username=username).exists():
            self.stdout.write(self.style.SUCCESS(
                f'Superuser "{username}" ya existe. No se crea de nuevo.'
            ))
            return

        Usuario.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            rol='superadmin',
        )
        self.stdout.write(self.style.SUCCESS(
            f'Superuser "{username}" creado exitosamente con rol superadmin.'
        ))
