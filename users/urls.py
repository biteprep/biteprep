# users/urls.py
from django.urls import path
from . import views
from .views import RateLimitedLoginView
from django.contrib.auth import views as auth_views

urlpatterns = [
    # Use custom rate-limited login view
    path('login/', RateLimitedLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup, name='signup'),
    path('signup/success/', views.signup_success, name='signup_success'),
    path('account/', views.account_page, name='account'),
    path('account/manage-subscription/', views.manage_subscription, name='manage_subscription'),
    path('account/delete/', views.delete_account, name='delete_account'),
    
    # Password reset views with rate limiting
    path('password_reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='registration/password_reset_form.html',
             email_template_name='registration/password_reset_email.html'
         ), 
         name='password_reset'),
    path('password_reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='registration/password_reset_done.html'
         ),
         name='password_reset_done'),
    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='registration/password_reset_confirm.html'
         ),
         name='password_reset_confirm'),
    path('reset/done/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='registration/password_reset_complete.html'
         ),
         name='password_reset_complete'),
]