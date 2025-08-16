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
# FIX: Import DatabaseError and logging
from django.db.utils import DatabaseError
import logging

# We must ensure Profile is imported if it exists
try:
    from users.models import Profile
except ImportError:
    Profile = None
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta

# Setup logger
logger = logging.getLogger(__name__)

# --- Custom Admin Site Definition ---

class BitePrepOTPAdminSite(OTPAdminSite):
    def index(self, request, extra_context=None):
        """Override the index view. Must be robust against DatabaseErrors during migration."""
        extra_context = extra_context or {}

        # Calculate KPIs
        today = timezone.now().date()
        last_7_days = today - timedelta(days=7)

        # Initialize defaults
        new_users_today = 0
        new_users_7d = 0
        active_subscriptions = 0
        total_answers_taken = 0
        live_questions = 0
        draft_questions = 0
        open_reports = 0
        new_inquiries = 0

        # FIX: Wrap all database access in a try/except block for resilience
        try:
            # User Stats
            new_users_today = User.objects.filter(date_joined__date=today).count()
            new_users_7d = User.objects.filter(date_joined__date__gte=last_7_days).count()
            
            # Subscription Stats
            if Profile:
                active_subscriptions = Profile.objects.filter(
                    Q(membership='Monthly') | Q(membership='Annual'),
                    membership_expiry_date__gte=today
                ).count()

            total_answers_taken = UserAnswer.objects.count()

            # Content and Support Stats (These rely on the 'status' column)
            # We use a nested try/except specifically for the status column issue.
            try:
                live_questions = Question.objects.filter(status='LIVE').count()
                draft_questions = Question.objects.filter(status='DRAFT').count()
                open_reports = QuestionReport.objects.filter(status='OPEN').count()
                new_inquiries = ContactInquiry.objects.filter(status='NEW').count()
            except DatabaseError:
                 # Fallback if the 'status' column specifically is missing
                 logger.warning("DatabaseError (Status Columns) in Admin Dashboard. Migrations may be incomplete. Using fallback values.")
                 live_questions = Question.objects.count() # Assume all are live if column missing
                 # Reports/Inquiries cannot be counted without status, remain 0.

        except DatabaseError as e:
            # Catch-all for broader database issues (e.g., tables don't exist yet)
            logger.error(f"General DatabaseError in Admin Dashboard: {e}. Initial migrations likely pending.")
            pass # All values remain at their defaults (0)


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
# This ensures all models registered via @admin.register() are available in our custom site.
for model, model_admin in site._registry.items():
    # We must check if the model is already registered to avoid potential conflicts
    if not otp_admin_site.is_registered(model):
        # Register the model with the specific admin class used in the default site
        try:
            # We use model_admin.__class__ to ensure we register the correct admin class instance
            otp_admin_site.register(model, model_admin.__class__)
        except admin.sites.AlreadyRegistered:
            # Handle cases where registration might be attempted multiple times
            pass

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
    path('accounts/password_change/',
         auth_views.PasswordChangeView.as_view(
             template_name='registration/password_change_form.html'
         ),
         name='password_change'),
    path('accounts/password_change/done/',
         auth_views.PasswordChangeDoneView.as_view(
             template_name='registration/password_change_done.html'
         ),
         name='password_change_done'),

    # Password Reset (When forgotten) - Requires Email Configuration
    path('accounts/password_reset/',
         auth_views.PasswordResetView.as_view(
             template_name='registration/password_reset_form.html',
             # Ensure it uses the custom email template provided
             email_template_name='registration/password_reset_email.html'
         ),
         name='password_reset'),
    path('accounts/password_reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='registration/password_reset_done.html'
         ),
         name='password_reset_done'),
    path('accounts/reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='registration/password_reset_confirm.html'
         ),
         name='password_reset_confirm'),
    path('accounts/reset/done/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='registration/password_reset_complete.html'
         ),
         name='password_reset_complete'),
         
    # Application URLs
    path('accounts/', include('users.urls')),
    path('', include('quiz.urls')),
]

# Serve media files locally ONLY if DEBUG is True AND we are using local storage.
if settings.DEBUG:
    # Check if the default storage backend is FileSystemStorage (local)
    # We use .get() safely in case STORAGES isn't configured correctly yet.
    is_local_storage = settings.STORAGES.get("default", {}).get("BACKEND") == "django.core.files.storage.FileSystemStorage"
    if is_local_storage:
        urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Admin Site customizations
otp_admin_site.site_header = "BitePrep Administration Console"
otp_admin_site.site_title = "BitePrep Admin"
otp_admin_site.index_title = "Management Dashboard"