# users/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Profile
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages

# A. Functionality: Custom Admin Action (Efficient Implementation)
@admin.action(description='Upgrade selected users to Annual (1 Year)')
def upgrade_to_annual(modeladmin, request, queryset):
    # Calculate the expiry date (Use timezone.now().date() for DateField compatibility)
    expiry_date = timezone.now().date() + timedelta(days=365)
    
    # Efficiently update the profiles related to the selected users in a single query
    user_ids = queryset.values_list('id', flat=True)
    
    # We update the Profile objects directly, filtering by the user IDs selected.
    updated_count = Profile.objects.filter(user_id__in=user_ids).update(
        membership='Annual',
        membership_expiry_date=expiry_date
    )
    
    # Provide feedback to the admin user
    modeladmin.message_user(request, f"Successfully upgraded {updated_count} users to Annual membership until {expiry_date.strftime('%Y-%m-%d')}.", messages.SUCCESS)

# Define an inline admin descriptor for Profile model
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'

# Define a new User admin
class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)
    actions = [upgrade_to_annual]

    # B. Performance: Optimize the query by selecting the related profile
    # This prevents N+1 queries when loading the user list.
    list_select_related = ('profile',)

    # A. Functionality: Methods to access related profile data
    def get_membership(self, obj):
        # We can safely access .profile because list_select_related is used
        # The try/except is a fallback if a profile somehow doesn't exist
        try:
            return obj.profile.membership
        except Profile.DoesNotExist:
            return "N/A (No Profile)"
    get_membership.short_description = 'Membership'
    get_membership.admin_order_field = 'profile__membership' # Allow sorting by the profile field

    def get_expiry_date(self, obj):
        try:
            return obj.profile.membership_expiry_date
        except Profile.DoesNotExist:
            return None
    get_expiry_date.short_description = 'Expiry Date'
    get_expiry_date.admin_order_field = 'profile__membership_expiry_date'

    # Update list_display to include the new methods
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_membership', 'get_expiry_date')
    
    # A. Functionality: Add filter by membership status
    # Appending to the default filters provided by BaseUserAdmin
    list_filter = BaseUserAdmin.list_filter + ('profile__membership',)


# Re-register UserAdmin
# Check if User is already registered before attempting to unregister (good practice)
if admin.site.is_registered(User):
    admin.site.unregister(User)
admin.site.register(User, UserAdmin)