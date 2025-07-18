# users/urls.py

from django.urls import path, include
from . import views

urlpatterns = [
    # This single line includes all of Django's built-in authentication views.
    # It handles login, logout, password change, and all password reset pages.
    # It will correctly look for templates inside the 'registration' folder.
    path('', include('django.contrib.auth.urls')), 
    
    # Your custom views remain below.
    path('signup/', views.signup, name='signup'),
    path('signup/success/', views.signup_success, name='signup_success'),
    
    # Your custom logout view overrides the default one from the include above
    # because it comes later in the list with the same 'logout' name.
    path('logout/', views.logout_view, name='logout'), 
    
    path('account/', views.account_page, name='account'),
    path('account/manage-subscription/', views.manage_subscription, name='manage_subscription'),
    path('account/delete/', views.delete_account, name='delete_account'),
]