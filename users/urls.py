# users/urls.py

from django.urls import path, include
from . import views

urlpatterns = [
    # This single line handles: login, logout, password change, password reset
    path('', include('django.contrib.auth.urls')), 
    
    # Your custom views
    path('signup/', views.signup, name='signup'),
    path('signup/success/', views.signup_success, name='signup_success'),
    # Your custom logout view overrides the default from the include above
    path('logout/', views.logout_view, name='logout'), 
    path('account/', views.account_page, name='account'),
    path('account/manage-subscription/', views.manage_subscription, name='manage_subscription'),
    path('account/delete/', views.delete_account, name='delete_account'),
]