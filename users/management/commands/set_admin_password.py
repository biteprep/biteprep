# users/management/commands/set_admin_password.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
import os

class Command(BaseCommand):
    help = 'Finds a user and sets their password from environment variables.'

    def handle(self, *args, **options):
        username = os.getenv('ADMIN_USERNAME')
        password = os.getenv('ADMIN_PASSWORD')

        if not username or not password:
            self.stdout.write(self.style.ERROR('ADMIN_USERNAME and ADMIN_PASSWORD environment variables must be set.'))
            return

        try:
            user = User.objects.get(username=username)
            user.set_password(password)
            # Also ensure the user is staff and superuser
            user.is_staff = True
            user.is_superuser = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Successfully set password and promoted user "{username}"'))
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User "{username}" does not exist. The createsuperuser command may need to run first.'))