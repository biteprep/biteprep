# quiz/management/commands/fix_axes.py
from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Ensure axes migrations are applied'

    def handle(self, *args, **options):
        self.stdout.write('Running axes migrations...')
        try:
            # Try to migrate axes specifically
            call_command('migrate', 'axes', verbosity=2)
            self.stdout.write(self.style.SUCCESS('Successfully migrated axes'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error migrating axes: {e}'))
        
        # Run all migrations
        self.stdout.write('Running all migrations...')
        call_command('migrate', verbosity=2)
        self.stdout.write(self.style.SUCCESS('All migrations complete'))