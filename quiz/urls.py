# quiz/urls.py (Complete file for Incorrect Review Feature)

from django.urls import path
from . import views

urlpatterns = [
    # Main site pages
    path('', views.landing_page, name='home'),
    path('contact/', views.contact_page, name='contact'),
    path('quiz/setup/', views.quiz_setup, name='quiz_setup'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('membership/', views.membership_page, name='membership_page'),

    # Quiz Player flow
    path('quiz/start/', views.start_quiz, name='start_quiz'),
    path('quiz/play/<int:question_index>/', views.quiz_player, name='quiz_player'),
    path('quiz/report-question/', views.report_question, name='report_question'),
    path('quiz/results/', views.quiz_results, name='quiz_results'),

    # Stripe checkout flow
    path('create-checkout-session/', views.create_checkout_session, name='create_checkout_session'),
    path('success/', views.success_page, name='success_page'),
    path('cancel/', views.cancel_page, name='cancel_page'),
    path('stripe-webhook/', views.stripe_webhook, name='stripe_webhook'),
    
    # Dashboard actions
    path('dashboard/reset/', views.reset_performance, name='reset_performance'),
    # --- NEW URL PATTERN ---
    path('quiz/start/incorrect/', views.start_incorrect_quiz, name='start_incorrect_quiz'),
]