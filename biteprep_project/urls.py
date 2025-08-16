# biteprep_project/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django_otp.admin import OTPAdminSite
from django.contrib.admin.sites import site
# Import the built-in authentication views
from django.contrib.auth import views as auth_views

# Imports for the Custom Dashboard
from django.contrib.auth.models import User
from quiz.models import Question, UserAnswer, QuestionReport, ContactInquiry
# We must ensure Profile is imported if it exists
try:
    from users.models import Profile
except ImportError:
    Profile = None
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta

# --- Custom Admin Site Definition ---

class BitePrepOTPAdminSite(OTPAdminSite):
    def index(self, request, extra_context=None):
        """Override the index view to add custom dashboard data."""
        extra_context = extra_context or {}

        # Calculate KPIs
        today = timezone.now().date()
        last_7_days = today - timedelta(days=7)

        # User Stats
        new_users_today = User.objects.filter(date_joined__date=today).count()
        new_users_7d = User.objects.filter(date_joined__date__gte=last_7_days).count()
        
        # Subscription Stats (Active means expiry date is today or in the future)
        active_subscriptions = 0
        if Profile:
            active_subscriptions = Profile.objects.filter(
                Q(membership='Monthly') | Q(membership='Annual'),
                membership_expiry_date__gte=today
            ).count()

        # Content Stats
        # Show both LIVE and DRAFT counts
        live_questions = Question.objects.filter(status='LIVE').count()
        draft_questions = Question.objects.filter(status='DRAFT').count()
        total_answers_taken = UserAnswer.objects.count()

        # Support Stats
        open_reports = QuestionReport.objects.filter(status='OPEN').count()
        new_inquiries = ContactInquiry.objects.filter(status='NEW').count()

        # Add stats to context
        extra_context['dashboard_stats'] = {
            'new_users_today': new_users_today,
            'new_users_7d': new_users_7d,
            'active_subscriptions': active_subscriptions,
            'live_questions': live_questions,
            'draft_questions': draft_questions,
            'total_answers_taken': total_answers_taken,
            'open_reports': open_reports,
            'new_inquiries': new_inquiries,
        }
        
        return super().index(request, extra_context)

# Initialize the custom admin site
otp_admin_site = BitePrepOTPAdminSite()

# Copy registry from the default admin site (site) to the OTP-enabled site (otp_admin_site)
# This ensures all models registered via @admin.register() (including our enhanced UserAdmin/QuestionAdmin) are available in our custom site.
for model, model_admin in site._registry.items():
    # We must check if the model is already registered to avoid potential conflicts
    if not otp_admin_site.is_registered(model):
        # Register the model with the specific admin class used in the default site
        otp_admin_site.register(model, model_admin.__class__)

# SECRET_ADMIN_PATH is loaded dynamically from settings.SECRET_ADMIN_PATH

urlpatterns = [
    # Honeypot URL
    path('admin/', include('admin_honeypot.urls', namespace='admin_honeypot')),
    # Real, secured admin URL using the custom admin site
    path(settings.SECRET_ADMIN_PATH, otp_admin_site.urls),
    path('impersonate/', include('impersonate.urls')),

    # --- Explicitly define auth routes ---
     
    # Login/Logout
    path('accounts/login/',
        auth_views.LoginView.as_view(
            template_name='registration/login.html'
        ),
        name='login'),
    path('accounts/logout/',
        auth_views.LogoutView.as_view(),
        name='logout'),

    # Password Change (While logged in)
    # ... (Password change routes remain the same)

    # Password Reset (When forgotten) - Requires Email Configuration
    # ... (Password reset routes remain the same)
         
    # Application URLs
    path('accounts/', include('users.urls')),
    path('', include('quiz.urls')),
]

# Serve media files locally ONLY if DEBUG is True AND we are using local storage.
if settings.DEBUG:
    # Check if the default storage backend is FileSystemStorage (local)
    is_local_storage = settings.STORAGES.get("default", {}).get("BACKEND") == "django.core.files.storage.FileSystemStorage"
    if is_local_storage:
        urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Admin Site customizations
otp_admin_site.site_header = "BitePrep Administration Console"
otp_admin_site.site_title = "BitePrep Admin"
otp_admin_site.index_title = "Management Dashboard"