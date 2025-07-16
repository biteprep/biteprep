# users/urls.py

from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Existing Auth URLs
    path('login/', auth_views.LoginView.as_view(template_name='users/login.html'), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup, name='signup'),
    
    # ADD THIS NEW URL
    path('signup/success/', views.signup_success, name='signup_success'),

    # Account Management URLs
    path('account/', views.account_page, name='account'),
    path('account/manage-subscription/', views.manage_subscription, name='manage_subscription'),
    path('account/delete/', views.delete_account, name='delete_account'),
    
    # Password Change URLs
    path('password-change/', auth_views.PasswordChangeView.as_view(
        template_name='users/password_change_form.html',
        success_url=reverse_lazy('password_change_done')
    ), name='password_change'),
    path('password-change/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='users/password_change_done.html'
    ), name='password_change_done'),
]