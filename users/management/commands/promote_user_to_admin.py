# users/management/commands/promote_user_to_admin.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
import os

class Command(BaseCommand):
    help = 'Finds a user and promotes them to be a full superuser.'

    def handle(self, *args, **options):
        username = os.getenv('ADMIN_USERNAME')
        if not username:
            self.stdout.write(self.style.ERROR('ADMIN_USERNAME environment variable must be set.'))
            return

        try:
            user = User.objects.get(username=username)
            user.is_staff = True
            user.is_superuser = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Successfully promoted user "{username}" to full superuser.'))
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User "{username}" does not exist. Please check the username.'))