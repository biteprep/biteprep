# biteprep_project/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django_otp.admin import OTPAdminSite
from django.contrib.admin.sites import site
# Import the built-in authentication views
from django.contrib.auth import views as auth_views

otp_admin_site = OTPAdminSite()
# Copy registry from the default admin site to the OTP-enabled site
for model, model_admin in site._registry.items():
    # We must check if the model is already registered to avoid potential conflicts
    if not otp_admin_site.is_registered(model):
        otp_admin_site.register(model, model_admin.__class__)

# SECRET_ADMIN_PATH is loaded dynamically from settings.SECRET_ADMIN_PATH

urlpatterns = [
    # Honeypot URL
    path('admin/', include('admin_honeypot.urls', namespace='admin_honeypot')),
    # Real, secured admin URL
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
    is_local_storage = settings.STORAGES.get("default", {}).get("BACKEND") == "django.core.files.storage.FileSystemStorage"
    if is_local_storage:
        urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Admin Site customizations
otp_admin_site.site_header = "BitePrep Administration Console"
otp_admin_site.site_title = "BitePrep Admin"
otp_admin_site.index_title = "Management Dashboard"