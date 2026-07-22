"""
Management command para crear/actualizar el superuser en deploy.
Lee ADMIN_USERNAME y ADMIN_PASSWORD de las variables de entorno.
Si el usuario ya existe, actualiza su password y flags.
Idempotente — seguro de correr en cada deploy.

Uso:
    python manage.py crear_superuser

En el Build Command de Render agregar al final:
    && python manage.py crear_superuser
"""
import os

from django.core.management.base import BaseCommand

from apps.cuentas.models import Usuario


class Command(BaseCommand):
    help = 'Crea o actualiza el superuser (lee credenciales de env vars)'

    def handle(self, *args, **options):
        username = os.environ.get('ADMIN_USERNAME', 'admin')
        password = os.environ.get('ADMIN_PASSWORD', '')
        email = os.environ.get('ADMIN_EMAIL', 'admin@norware.com')

        if not password:
            self.stdout.write(self.style.WARNING(
                'ADMIN_PASSWORD no está definido. Saltando creación de superuser.'
            ))
            return

        user, created = Usuario.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'rol': 'superadmin',
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
            },
        )

        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(
                f'Superuser "{username}" creado exitosamente.'
            ))
        else:
            # Asegurar que el usuario existente tenga los flags correctos
            changed = False
            if not user.is_staff:
                user.is_staff = True
                changed = True
            if not user.is_superuser:
                user.is_superuser = True
                changed = True
            if not user.is_active:
                user.is_active = True
                changed = True
            if user.rol != 'superadmin':
                user.rol = 'superadmin'
                changed = True

            # Siempre actualizar la password por si cambió en env vars
            user.set_password(password)
            changed = True

            if changed:
                user.save()
                self.stdout.write(self.style.SUCCESS(
                    f'Superuser "{username}" actualizado (password + flags).'
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f'Superuser "{username}" ya está correctamente configurado.'
                ))
