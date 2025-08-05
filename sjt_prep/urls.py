from django.urls import path
from . import views

# Define an app name for namespacing
app_name = 'sjt_prep'

urlpatterns = [
    path('setup/', views.sjt_setup, name='sjt_setup'),
    path('start/', views.start_sjt_exam, name='start_sjt_exam'),
    # The main exam player (SPA-like interface)
    path('exam/', views.sjt_exam_player, name='sjt_exam_player'),
    # AJAX endpoint for saving answers
    path('submit_answers/', views.submit_sjt_answers, name='submit_sjt_answers'),
    path('results/', views.sjt_results, name='sjt_results'),
]