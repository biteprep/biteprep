# users/urls.py

from django.urls import path, include
from django.contrib.auth import views as auth_views # Import Django's built-in auth views
from . import views

urlpatterns = [
    # Custom Views (should come first to ensure they are matched before the generic include)
    path('signup/', views.signup, name='signup'),
    path('signup/success/', views.signup_success, name='signup_success'),
    path('logout/', views.logout_view, name='logout'), 
    path('account/', views.account_page, name='account'),
    path('account/manage-subscription/', views.manage_subscription, name='manage_subscription'),
    path('account/delete/', views.delete_account, name='delete_account'),
    
    # Explicit Password Change URLs
    # We point to Django's built-in views but explicitly name the templates to use.
    path(
        'password_change/', 
        auth_views.PasswordChangeView.as_view(
            template_name='registration/password_change_form.html',
            success_url='/accounts/password_change/done/' # Redirect to the done page on success
        ), 
        name='password_change'
    ),
    path(
        'password_change/done/',
        auth_views.PasswordChangeDoneView.as_view(
            template_name='registration/password_change_done.html'
        ),
        name='password_change_done'
    ),

    # Generic Include for the rest (login, password_reset, etc.)
    # This should come after the explicit URLs to avoid conflicts.
    path('', include('django.contrib.auth.urls')), 
]