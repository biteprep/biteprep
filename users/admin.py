# users/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Profile
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages
from django.utils.html import format_html
from django.urls import reverse
from django.conf import settings # Import settings for Stripe URL logic

# Import for History/Audit Log
from simple_history.admin import SimpleHistoryAdmin

# A. Functionality: Custom Admin Action
@admin.action(description='Upgrade selected users to Annual (1 Year)')
def upgrade_to_annual(modeladmin, request, queryset):
    expiry_date = timezone.now().date() + timedelta(days=365)
    user_ids = queryset.values_list('id', flat=True)
    updated_count = Profile.objects.filter(user_id__in=user_ids).update(
        membership='Annual',
        membership_expiry_date=expiry_date
    )
    modeladmin.message_user(request, f"Successfully upgraded {updated_count} users to Annual membership until {expiry_date.strftime('%Y-%m-%d')}.", messages.SUCCESS)

# Define an inline admin descriptor for Profile model
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'
    
    # ENHANCEMENT: Add the Stripe link to the readonly fields
    readonly_fields = ('stripe_link',)

    # ENHANCEMENT: Method to generate a clickable link to the Stripe Dashboard
    def stripe_link(self, obj):
        if obj.stripe_customer_id:
            # Determine if we should use the live or test Stripe dashboard URL.
            # Check DEBUG status or if the secret key is explicitly a test key.
            is_test_mode = settings.DEBUG or (settings.STRIPE_SECRET_KEY and settings.STRIPE_SECRET_KEY.startswith('sk_test_'))
            
            if is_test_mode:
                base_url = "https://dashboard.stripe.com/test/customers/"
            else:
                base_url = "https://dashboard.stripe.com/customers/"
                
            url = f"{base_url}{obj.stripe_customer_id}"
            # Display as a button
            return format_html('<a href="{}" target="_blank" class="button">View on Stripe</a>', url)
        return "N/A"
    stripe_link.short_description = 'Stripe Dashboard'


# Define a new User admin
# Inherit from SimpleHistoryAdmin AND BaseUserAdmin
class UserAdmin(SimpleHistoryAdmin, BaseUserAdmin):
    inlines = (ProfileInline,)
    actions = [upgrade_to_annual]

    # B. Performance: Optimize the query by selecting the related profile
    list_select_related = ('profile',)

    # A. Functionality: Methods to access related profile data
    def get_membership(self, obj):
        try:
            return obj.profile.membership
        except Profile.DoesNotExist:
            return "N/A (No Profile)"
    get_membership.short_description = 'Membership'
    get_membership.admin_order_field = 'profile__membership'

    def get_expiry_date(self, obj):
        try:
            return obj.profile.membership_expiry_date
        except Profile.DoesNotExist:
            return None
    get_expiry_date.short_description = 'Expiry Date'
    get_expiry_date.admin_order_field = 'profile__membership_expiry_date'

    # ENHANCEMENT: Add Impersonation Link
    def impersonate_link(self, obj):
        # Best practice: Only allow impersonation if the target user is not staff/superuser
        if not obj.is_staff and not obj.is_superuser:
            url = reverse("impersonate-start", args=[obj.id])
            # Display as a button for better visibility
            return format_html('<a href="{}" class="button">Impersonate</a>', url)
        return "-"
    impersonate_link.short_description = 'Support Login'

    # Update list_display to include the new methods, activity dates, and impersonation link
    list_display = ('username', 'email', 'get_membership', 'get_expiry_date', 'last_login', 'date_joined', 'is_staff', 'impersonate_link')
    
    # A. Functionality: Add filter by membership status
    list_filter = BaseUserAdmin.list_filter + ('profile__membership',)


# Re-register UserAdmin
if admin.site.is_registered(User):
    admin.site.unregister(User)
admin.site.register(User, UserAdmin)