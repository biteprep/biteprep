# biteprep_project/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django_otp.admin import OTPAdminSite

# This is no longer needed here as users/views.py has a custom logout
# from users import views as user_views

# --- Admin Site Setup ---
admin.site.__class__ = OTPAdminSite
SECRET_ADMIN_PATH = 'manage-biteprep-secure-access/' 

urlpatterns = [
    # Admin and third-party apps
    path('admin/', include('admin_honeypot.urls', namespace='admin_honeypot')),
    path(SECRET_ADMIN_PATH, admin.site.urls),
    path('impersonate/', include('impersonate.urls')),
    
    # NEW: Include Django's built-in auth URLs directly at the project level.
    # This includes login, logout, password_change, password_reset, etc.
    path('accounts/', include('django.contrib.auth.urls')),

    # NEW: Include your custom user URLs (signup, account page, etc.)
    # They will share the same /accounts/ prefix.
    path('accounts/', include('users.urls')),
    
    # All other app URLs are at the root
    path('', include('quiz.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Customize Admin titles
admin.site.site_header = "BitePrep Administration Console"
admin.site.site_title = "BitePrep Admin"
admin.site.index_title = "Management Dashboard"