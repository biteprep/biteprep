# biteprep_project/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django_otp.admin import OTPAdminSite
from django.contrib.admin.sites import site

# Create a new, isolated instance of the OTP admin site.
otp_admin_site = OTPAdminSite()

# This loop finds all models registered with the default admin site and also registers them with our new OTP site.
for model, model_admin in site._registry.items():
    otp_admin_site.register(model, model_admin.__class__)

SECRET_ADMIN_PATH = 'manage-biteprep-secure-access/' 

urlpatterns = [
    # Admin and third-party apps
    path('admin/', include('admin_honeypot.urls', namespace='admin_honeypot')),
    path(SECRET_ADMIN_PATH, otp_admin_site.urls),
    path('impersonate/', include('impersonate.urls')),
    
    # All account management URLs (built-in and custom)
    path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/', include('users.urls')),
    
    # The main quiz app URLs
    path('', include('quiz.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Customize our new admin instance
otp_admin_site.site_header = "BitePrep Administration Console"
otp_admin_site.site_title = "BitePrep Admin"
otp_admin_site.index_title = "Management Dashboard"