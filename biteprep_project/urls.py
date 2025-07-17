# users/urls.py

from django.urls import path, include
from . import views

urlpatterns = [
    # This line includes all of Django's built-in authentication views
    # (login, logout, password reset, password change, etc.)
    path('', include('django.contrib.auth.urls')), 
    
    # Your custom views
    path('signup/', views.signup, name='signup'),
    path('signup/success/', views.signup_success, name='signup_success'),
    # This custom logout view will override the default one included above
    path('logout/', views.logout_view, name='logout'), 
    path('account/', views.account_page, name='account'),
    path('account/manage-subscription/', views.manage_subscription, name='manage_subscription'),
    path('account/delete/', views.delete_account, name='delete_account'),
]