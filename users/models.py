from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    # The one-to-one link to the built-in User model
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    # Define the choices for membership types
    MEMBERSHIP_CHOICES = [
        ('Free', 'Free'),
        ('Monthly', 'Monthly'),
        ('Annual', 'Annual'),
    ]

    # The field to store the user's current membership status
    membership = models.CharField(max_length=10, choices=MEMBERSHIP_CHOICES, default='Free')
    
    # A field to store when a paid membership expires
    membership_expiry_date = models.DateField(null=True, blank=True)

    # Field to store the Stripe Customer ID, linked to their subscription
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True)

    # This makes the object display nicely in the admin panel
    def __str__(self):
        return f'{self.user.username} Profile'