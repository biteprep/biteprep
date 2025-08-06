# biteprep_project/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# C. Security (2FA): Imports for django-otp
from django_otp.admin import OTPAdminSite
# Import to ensure TOTP models register correctly with the admin (required even if unused)
import django_otp.plugins.otp_totp.admin 

# C. Security (2FA): Replace the default admin site class with the OTP-enforced one.
# This enforces 2FA for all staff users accessing the admin panel.
admin.site.__class__ = OTPAdminSite

# C. Security (Obscure URL): Define the secret admin path.
# !!! IMPORTANT: Ensure this is your unique, secret path !!!
SECRET_ADMIN_PATH = 'manage-biteprep-secure-access/' 

urlpatterns = [
    # C. Security (Honeypot): The FAKE admin login page at the default URL.
    path('admin/', include('admin_honeypot.urls', namespace='admin_honeypot')),

    # C. Security (Obscure URL): The REAL, secret admin login page (OTP Protected).
    path(SECRET_ADMIN_PATH, admin.site.urls),

    # Impersonation URLs
    path('impersonate/', include('impersonate.urls')),
    
    # All user-related URLs will be under /accounts/
    path('accounts/', include('users.urls')),
    # All other app URLs are at the root
    path('', include('quiz.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Customize Admin titles (Optional Enhancement)
admin.site.site_header = "BitePrep Administration Console"
admin.site.site_title = "BitePrep Admin"
admin.site.index_title = "Management Dashboard"