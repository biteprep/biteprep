# quiz/views.py

import random
import stripe
import json
# Ensure datetime and timezone are imported correctly
from datetime import date, datetime, timedelta
from django.utils import timezone
# Import Decimal for precise score calculations
from decimal import Decimal, ROUND_HALF_UP
from django.shortcuts import render, redirect, HttpResponse
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.contrib import messages
from django.urls import reverse
from .models import Category, Question, Answer, UserAnswer, FlaggedQuestion, QuestionReport
from .forms import ContactForm

# Import Profile model for webhook processing
try:
    from users.models import Profile
except ImportError:
    Profile = None

import logging

# Set up logging (Configured in settings.py)
logger = logging.getLogger(__name__)

MAX_QUESTIONS_PER_QUIZ = 500

# (landing_page, contact_page, terms_page, privacy_page, cookie_page, membership_page remain the same)
# ... (omitted for brevity, use your existing implementations) ...

@login_required
def dashboard(request):
    # (dashboard implementation remains the same)
    # ... (omitted for brevity, use your existing implementation) ...
    return render(request, 'quiz/dashboard.html', context)

@login_required
def quiz_setup(request):
    if request.method == 'POST':
        # (Validation logic remains the same)
        profile = request.user.profile
        is_active_subscription = profile.membership_expiry_date and profile.membership_expiry_date >= date.today()
        if not (profile.membership == 'Free' or is_active_subscription):
            messages.warning(request, "Your subscription has expired. Please renew your plan.")
            return redirect('membership_page')
        
        selected_subtopic_ids = request.POST.getlist('subtopics')
        if not selected_subtopic_ids:
            messages.info(request, "Please select at least one topic to start a quiz.")
            return redirect('quiz_setup')
        
        question_filter = request.POST.get('question_filter', 'all')

        # CRITICAL UPDATE: Only fetch questions that are LIVE
        questions = Question.objects.filter(
            subtopic__id__in=selected_subtopic_ids,
            status='LIVE' 
        )
        
        if question_filter == 'unanswered':
            answered_question_ids = UserAnswer.objects.filter(user=request.user).values_list('question_id', flat=True)
            questions = questions.exclude(id__in=answered_question_ids)
        elif question_filter == 'correct':
            questions = questions.filter(id__in=UserAnswer.objects.filter(user=request.user, is_correct=True).values_list('question_id', flat=True))
        elif question_filter == 'incorrect':
            questions = questions.filter(id__in=UserAnswer.objects.filter(user=request.user, is_correct=False).values_list('question_id', flat=True))
        
        question_ids = list(questions.values_list('id', flat=True).distinct())
        
        if not question_ids:
            # Updated message to reflect potential content updates
            messages.info(request, "No live questions found for your selected topics and filters. We may be updating our content.")
            return redirect('quiz_setup')
        
        random.shuffle(question_ids)
        
        # Handle question count limits
        # ... (logic remains the same) ...

        # Initialize quiz context
        quiz_mode = request.POST.get('quiz_mode', 'quiz')
        quiz_context = {
            'question_ids': question_ids, 'total_questions': len(question_ids),
            'mode': quiz_mode, 'user_answers': {},
            'penalty_value': 0.0
        }

        # Handle Timer
        # ... (logic remains the same) ...

        # Handle Negative Marking (Allowed for BOTH Quiz and Test modes)
        # This logic is correct.
        if 'negative-marking-toggle' in request.POST:
            try:
                penalty = float(request.POST.get('penalty_value', 0.0))
                if penalty > 0:
                    quiz_context['penalty_value'] = penalty
            except (ValueError, TypeError):
                messages.warning(request, "Invalid penalty value ignored.")
                pass

        request.session['quiz_context'] = quiz_context
        return redirect('start_quiz')

    categories = Category.objects.prefetch_related('topics__subtopics').all()
    context = {'categories': categories}
    return render(request, 'quiz/quiz_setup.html', context)

# (start_quiz, quiz_player, quiz_results, reset_performance implementations remain the same as the previous interaction)
# ... (omitted for brevity, use your existing implementations for these functions) ...

@login_required
def start_incorrect_quiz(request):
    # CRITICAL UPDATE: Ensure we only select LIVE questions that were answered incorrectly.
    question_ids = list(UserAnswer.objects.filter(
        user=request.user, 
        is_correct=False,
        question__status='LIVE' # Filter by status
    ).values_list('question_id', flat=True).distinct())
    
    if not question_ids:
        messages.success(request, "Great job! You have no incorrect answers to review.")
        return redirect('dashboard')
    random.shuffle(question_ids)
    request.session['quiz_context'] = {'question_ids': question_ids, 'total_questions': len(question_ids), 'mode': 'quiz', 'user_answers': {}, 'penalty_value': 0.0}
    return redirect('start_quiz')

@login_required
def start_flagged_quiz(request):
    # CRITICAL UPDATE: Ensure we only select LIVE questions that were flagged.
    question_ids = list(FlaggedQuestion.objects.filter(
        user=request.user,
        question__status='LIVE' # Filter by status
    ).values_list('question_id', flat=True))
    
    if not question_ids:
        messages.info(request, "You have not flagged any questions for review.")
        return redirect('dashboard')
    random.shuffle(question_ids)
    request.session['quiz_context'] = {'question_ids': question_ids, 'total_questions': len(question_ids), 'mode': 'quiz', 'user_answers': {}, 'penalty_value': 0.0}
    return redirect('start_quiz')


# (report_question, create_checkout_session, success_page, cancel_page, stripe_webhook, handle_subscription_update, handle_subscription_deletion remain the same)
# ... (functions omitted for brevity, use your existing implementations)