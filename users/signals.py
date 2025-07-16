# users/signals.py

from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import Profile

# This function will run every time a User object is saved
@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    # 'created' is a boolean that is True if the save operation created a new object
    if created:
        Profile.objects.create(user=instance)