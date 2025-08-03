# quiz/views.py
import random
import stripe
import json
import os
from datetime import date, datetime, timedelta
import traceback
from django.shortcuts import render, redirect
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from .models import Category, Question, Answer, UserAnswer, QuestionReport, ContactInquiry, Topic, FlaggedQuestion
from users.models import Profile
from .forms import ContactForm

# Define a constant for maximum quiz size to prevent session overflow (Bug #3 Fix)
MAX_QUESTIONS_PER_QUIZ = 500

@login_required
def quiz_setup(request):
    if request.method == 'POST':
        profile = request.user.profile
        if not (profile.membership == 'Free' or (profile.membership_expiry_date and profile.membership_expiry_date >= date.today())):
            messages.warning(request, "Your subscription has expired. Please renew your plan to continue.")
            return redirect('membership_page')
        
        selected_subtopic_ids = request.POST.getlist('subtopics')
        if not selected_subtopic_ids:
            messages.info(request, "Please select at least one topic to start a quiz.")
            return redirect('quiz_setup')
            
        question_filter = request.POST.get('question_filter', 'all')
        questions = Question.objects.filter(subtopic__id__in=selected_subtopic_ids)
        
        if question_filter == 'unanswered':
            answered_question_ids = UserAnswer.objects.filter(user=request.user).values_list('question_id', flat=True)
            questions = questions.exclude(id__in=answered_question_ids)
        elif question_filter == 'correct':
            questions = questions.filter(id__in=UserAnswer.objects.filter(user=request.user, is_correct=True).values_list('question_id', flat=True))
        elif question_filter == 'incorrect':
            questions = questions.filter(id__in=UserAnswer.objects.filter(user=request.user, is_correct=False).values_list('question_id', flat=True))
            
        question_ids = list(questions.values_list('id', flat=True))
        random.shuffle(question_ids)
        
        question_count_type = request.POST.get('question_count_type', 'all')
        
        if profile.membership == 'Free':
            FREE_TIER_LIMIT = 10
            # Check length before slicing to ensure the message is accurate if they have exactly the limit or more
            if len(question_ids) >= FREE_TIER_LIMIT:
                 messages.info(request, f"As a free user, your quiz is limited to {FREE_TIER_LIMIT} questions.")
            question_ids = question_ids[:FREE_TIER_LIMIT]

        elif question_count_type == 'custom':
            try:
                custom_count = int(request.POST.get('question_count_custom', 0))
                if custom_count > 0:
                    question_ids = question_ids[:custom_count]
            except (ValueError, TypeError):
                pass

        # Bug #3 Fix: Enforce a hard limit to prevent session data issues.
        if len(question_ids) > MAX_QUESTIONS_PER_QUIZ:
            question_ids = question_ids[:MAX_QUESTIONS_PER_QUIZ]
            # Only show this message if the Free tier limit wasn't the reason for truncation
            if profile.membership != 'Free':
                messages.warning(request, f"To ensure stability, the quiz has been limited to the maximum of {MAX_QUESTIONS_PER_QUIZ} questions.")

        if not question_ids:
            messages.info(request, "No questions found for your selected topics and filters.")
            return redirect('quiz_setup')
            
        quiz_context = {
            'question_ids': question_ids, 'total_questions': len(question_ids),
            'mode': request.POST.get('quiz_mode', 'quiz'), 'user_answers': {},
        }
        
        if 'timer-toggle' in request.POST:
            try:
                timer_minutes = int(request.POST.get('timer_minutes', 0))
                if timer_minutes > 0:
                    quiz_context['start_time'] = timezone.now().isoformat()
                    quiz_context['duration_seconds'] = timer_minutes * 60
            except (ValueError, TypeError):
                pass
                
        request.session['quiz_context'] = quiz_context
        return redirect('start_quiz')
        
    categories = Category.objects.prefetch_related('topics__subtopics').all()
    context = {'categories': categories}
    return render(request, 'quiz/quiz_setup.html', context)

@login_required
def start_quiz(request):
    # (No changes needed here, but kept for completeness)
    if 'quiz_context' in request.session:
        request.session['quiz_context']['user_answers'] = {}
        request.session.modified = True
        return redirect('quiz_player', question_index=1)
    messages.error(request, "Could not start quiz. Please try setting it up again.")
    return redirect('quiz_setup')

@login_required
def quiz_player(request, question_index):
    if 'quiz_context' not in request.session:
        messages.error(request, "Quiz session not found. Please start a new quiz.")
        return redirect('quiz_setup')
        
    quiz_context = request.session['quiz_context']
    question_ids = quiz_context.get('question_ids', [])
    quiz_mode = quiz_context.get('mode', 'quiz')
    
    if not (0 < question_index <= len(question_ids)):
        return redirect('quiz_results')
        
    question_id = question_ids[question_index - 1]
    is_feedback_mode = False
    
    if request.method == 'POST':
        action = request.POST.get('action')
        navigate_to = request.POST.get('navigate_to') # Bug #1: Check for sidebar navigation
        submitted_answer_id_str = request.POST.get('answer')

        # --- Answer Handling Logic (Bugs #1 and #2) ---
        
        user_answers = quiz_context.get('user_answers', {})
        current_info = user_answers.get(str(question_id), {}).copy()

        # Determine submission status (Bug #2)
        # Preserve existing status OR update if the current action is 'submit_answer' in quiz mode.
        is_submitted = current_info.get('is_submitted', False)
        if quiz_mode == 'quiz' and action == 'submit_answer':
            is_submitted = True

        # Save the selection if provided
        if submitted_answer_id_str:
            try:
                answer_obj = Answer.objects.get(id=int(submitted_answer_id_str))
                
                # Save the selection and the submission status
                quiz_context['user_answers'][str(question_id)] = { 
                    'answer_id': answer_obj.id, 
                    'is_correct': answer_obj.is_correct,
                    'is_submitted': is_submitted # Bug #2: Track submission state
                }
            except (Answer.DoesNotExist, ValueError):
                pass
        
        # Handle the case where 'submit_answer' was clicked but no answer was selected yet
        if is_submitted and str(question_id) not in quiz_context['user_answers']:
             quiz_context['user_answers'][str(question_id)] = {
                 'answer_id': None,
                 'is_correct': False, # No answer selected is considered incorrect
                 'is_submitted': True
             }

        if action == 'toggle_flag':
            flag, created = FlaggedQuestion.objects.get_or_create(user=request.user, question_id=question_id)
            if not created:
                flag.delete()
        
        request.session.modified = True

        # --- Navigation Logic ---

        # Bug #1: Handle Sidebar Navigation (must happen after saving answer)
        if navigate_to:
            try:
                target_index = int(navigate_to)
                if 0 < target_index <= len(question_ids):
                     # Redirect to the target question (POST-Redirect-GET pattern)
                     return redirect('quiz_player', question_index=target_index)
            except ValueError:
                pass

        if action == 'submit_answer' and quiz_mode == 'quiz':
            is_feedback_mode = True # Show feedback immediately after explicit submission
        elif action == 'prev' and question_index > 1:
            return redirect('quiz_player', question_index=question_index - 1)
        elif action == 'next' and question_index < len(question_ids):
            return redirect('quiz_player', question_index=question_index + 1)
        elif action == 'finish':
            return redirect('quiz_results')

    # --- Rendering Logic (GET or non-redirected POST) ---
            
    question = Question.objects.select_related('subtopic__topic').prefetch_related('answers').get(pk=question_id)
    
    # Timer logic (unchanged)
    seconds_remaining = None
    if 'start_time' in quiz_context:
        start_time = datetime.fromisoformat(quiz_context['start_time'])
        duration = timedelta(seconds=quiz_context.get('duration_seconds', 0))
        time_passed = timezone.now() - start_time
        seconds_remaining = max(0, int((duration - time_passed).total_seconds()))
        if seconds_remaining <= 0 and quiz_mode == 'test':
            messages.info(request, "Time is up! The quiz has been automatically submitted.")
            return redirect('quiz_results')
            
    user_flagged_question_ids = list(FlaggedQuestion.objects.filter(user=request.user).values_list('question_id', flat=True))
    navigator_items = []
    user_answers = quiz_context.get('user_answers', {})
    
    # Navigator visualization logic (Updated for Bug #2)
    for i, q_id in enumerate(question_ids):
        idx = i + 1
        answer_info = user_answers.get(str(q_id))
        button_class = 'btn-outline-secondary'
        
        if answer_info:
            if quiz_mode == 'test':
                 # In test mode, just show it is answered (using success as the original code did)
                 button_class = 'btn-success'
            elif quiz_mode == 'quiz':
                # In quiz mode, show correctness only if submitted (Bug #2)
                if answer_info.get('is_submitted'):
                     button_class = 'btn-success' if answer_info.get('is_correct') else 'btn-danger'
                else:
                    # Optional: Indicate answered but not submitted
                    button_class = 'btn-primary' 

        if idx == question_index:
            button_class = button_class.replace('btn-outline-', 'btn-') + ' active'
            
        navigator_items.append({ 'index': idx, 'class': button_class, 'is_flagged': q_id in user_flagged_question_ids })

    user_answer_info = user_answers.get(str(question_id))

    # Bug #2: Determine Feedback Mode based on 'is_submitted' status if navigating back
    if not is_feedback_mode and user_answer_info and quiz_mode == 'quiz':
        if user_answer_info.get('is_submitted', False):
            is_feedback_mode = True
            
    # Bug #1: Ensure the selected answer ID is passed to the context for the template to pre-check the radio button
    user_selected_answer_id = user_answer_info.get('answer_id') if user_answer_info else None
    
    user_answer_obj = None
    if is_feedback_mode and user_selected_answer_id:
        try:
            user_answer_obj = Answer.objects.get(id=user_selected_answer_id)
        except Answer.DoesNotExist:
            pass
            
    context = {
        'question': question, 'question_index': question_index, 'total_questions': len(question_ids),
        'quiz_context': quiz_context, 'is_feedback_mode': is_feedback_mode,
        'user_selected_answer_id': user_selected_answer_id, 'user_answer': user_answer_obj,
        'is_last_question': question_index == len(question_ids),
        'navigator_items': navigator_items, 'seconds_remaining': seconds_remaining,
        'flagged_questions': user_flagged_question_ids,
    }
    return render(request, 'quiz/quiz_player.html', context)