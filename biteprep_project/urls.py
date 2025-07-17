# biteprep_project/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    # This correctly points to the urls.py file inside your 'quiz' app
    path('', include('quiz.urls')),
    # This correctly points to the urls.py file inside your 'users' app
    path('accounts/', include('users.urls')),
]

# This is the standard pattern to serve user-uploaded media files (like question images)
# during local development (when DEBUG is True).
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)