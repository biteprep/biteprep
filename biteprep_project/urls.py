from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django_otp.admin import OTPAdminSite
import django_otp.plugins.otp_totp.admin

# Replace the default admin site class with the OTP-enforced one.
admin.site.__class__ = OTPAdminSite

# Define the secret admin path.
SECRET_ADMIN_PATH = 'manage-biteprep-secure-access/'

urlpatterns = [
    # Security: Fake admin login page at the default URL.
    path('admin/', include('admin_honeypot.urls', namespace='admin_honeypot')),

    # Security: Real, secret admin login page.
    path(SECRET_ADMIN_PATH, admin.site.urls),

    # Admin Enhancements: User Impersonation URLs
    path('impersonate/', include('impersonate.urls')),
    
    # App URLs
    path('accounts/', include('users.urls')),
    path('sjt/', include('sjt_prep.urls', namespace='sjt_prep')), # <<< ADDED NEW APP
    path('', include('quiz.urls')), # Main quiz app at the root
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Customize Admin titles
admin.site.site_header = "BitePrep Administration Console"
admin.site.site_title = "BitePrep Admin"
admin.site.index_title = "Management Dashboard"