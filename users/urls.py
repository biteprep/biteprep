# users/urls.py

from django.urls import path
from . import views

# This app now only handles custom user-related views.
urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('signup/success/', views.signup_success, name='signup_success'),
    path('account/', views.account_page, name='account'),
    path('account/manage-subscription/', views.manage_subscription, name='manage_subscription'),
    path('account/delete/', views.delete_account, name='delete_account'),
]