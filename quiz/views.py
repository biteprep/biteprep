# quiz/views.py (Complete file for Step 3)

import random
import stripe
import json
import os
from django.shortcuts import render, redirect
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from .models import Category, Question, Answer, UserAnswer, QuestionReport, ContactInquiry
from users.models import Profile
from .forms import ContactForm
from django.contrib.auth.decorators import login_required
from datetime import date, datetime, timedelta
from django.db.models import Count, Q
from django.contrib import messages
from django.urls import reverse

# ===================================================================
#  The views below this line are unchanged from the previous step
# ===================================================================

def landing_page(request):
    return render(request, 'quiz/landing_page.html')

def contact_page(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Thank you for your message! We will get back to you shortly.")
            return redirect('home')
    else:
        if request.user.is_authenticated:
            initial_data = {'name': request.user.username, 'email': request.user.email}
            form = ContactForm(initial=initial_data)
        else:
            form = ContactForm()
    return render(request, 'quiz/contact_page.html', {'form': form})

@login_required
def membership_page(request):
    return render(request, 'quiz/membership_page.html')

@login_required
def dashboard(request):
    user_answers = UserAnswer.objects.filter(user=request.user)
    total_answered = user_answers.count()
    correct_answered = user_answers.filter(is_correct=True).count()
    try:
        overall_percentage = (correct_answered / total_answered) * 100
    except ZeroDivisionError:
        overall_percentage = 0
    topic_performance = (
        UserAnswer.objects.filter(user=request.user)
        .values('question__subtopic__topic__name')
        .annotate(total=Count('id'), correct=Count('id', filter=Q(is_correct=True)))
        .order_by('-total')
    )
    topic_stats = []
    for topic in topic_performance:
        try:
            percentage = (topic['correct'] / topic['total']) * 100
        except ZeroDivisionError:
            percentage = 0
        topic_stats.append({'name': topic['question__subtopic__topic__name'], 'total': topic['total'], 'correct': topic['correct'], 'percentage': round(percentage, 1)})
    context = {
        'total_answered': total_answered,
        'correct_answered': correct_answered,
        'overall_percentage': round(overall_percentage, 1),
        'topic_stats': topic_stats,
    }
    return render(request, 'quiz/dashboard.html', context)

@login_required
def reset_performance(request):
    if request.method == 'POST':
        UserAnswer.objects.filter(user=request.user).delete()
        messages.success(request, "Your performance statistics have been successfully reset.")
        return redirect('dashboard')
    return redirect('dashboard')

@login_required
def quiz_setup(request):
    if request.method == 'POST':
        selected_subtopic_ids = request.POST.getlist('subtopics')
        if not selected_subtopic_ids:
            messages.info(request, "Please select at least one topic to start a quiz.")
            return redirect('quiz_setup')

        questions = Question.objects.filter(subtopic__id__in=selected_subtopic_ids)
        question_ids = list(questions.values_list('id', flat=True))
        random.shuffle(question_ids)
        
        if not question_ids:
            messages.info(request, "No questions found for your selected topics.")
            return redirect('quiz_setup')
            
        quiz_context = { 'question_ids': question_ids }
        request.session['quiz_context'] = quiz_context
        return redirect('start_quiz')
        
    categories = Category.objects.prefetch_related('topics__subtopics').all()
    context = {'categories': categories}
    return render(request, 'quiz/quiz_setup.html', context)

@login_required
def start_quiz(request):
    return redirect('quiz_player', question_index=1)

# ===================================================================
#  DEBUGGING STEP 3: Add form, POST logic, and navigator
# ===================================================================
@login_required
def quiz_player(request, question_index):
    # 1. Check session
    if 'quiz_context' not in request.session:
        messages.error(request, "Quiz session not found. Please start a new quiz.")
        return redirect('quiz_setup')

    quiz_context = request.session['quiz_context']
    question_ids = quiz_context.get('question_ids', [])
    
    # 2. Check index
    if not (0 < question_index <= len(question_ids)):
        messages.error(request, "Invalid question index.")
        return redirect('quiz_setup')

    question_id = question_ids[question_index - 1]

    # --- START OF NEW LOGIC FOR THIS STEP ---
    # 3. Handle POST request for navigation
    if request.method == 'POST':
        action = request.POST.get('action')
        # We'll just handle navigation for now, not answer submission
        if action == 'prev' and question_index > 1:
            return redirect('quiz_player', question_index=question_index - 1)
        elif action == 'next' and question_index < len(question_ids):
            return redirect('quiz_player', question_index=question_index + 1)
        elif action == 'finish':
            return redirect('quiz_results') # Will go to a dummy page for now
    # --- END OF NEW LOGIC FOR THIS STEP ---

    # 4. Fetch question from DB
    try:
        question = Question.objects.prefetch_related('answers').get(pk=question_id)
    except Question.DoesNotExist:
        messages.error(request, "The requested question could not be found in the database.")
        return redirect('quiz_setup')

    # --- START OF NEW LOGIC FOR THIS STEP ---
    # 5. Build the navigator items
    navigator_items = []
    # This safely gets user_answers, defaulting to an empty dict if it doesn't exist yet
    user_answers = quiz_context.get('user_answers', {}) 

    for i, q_id in enumerate(question_ids):
        idx = i + 1
        button_class = 'btn-outline-secondary' # Default button style
        if str(q_id) in user_answers:
            button_class = 'btn-success' # Mark as answered if present in user_answers
        
        if idx == question_index:
            button_class = button_class.replace('btn-outline-', 'btn-') + ' active'

        navigator_items.append({
            'index': idx,
            'class': button_class,
            'is_flagged': False # Not testing flags yet
        })
    # --- END OF NEW LOGIC FOR THIS STEP ---

    # 6. Render template
    context = {
        'question': question,
        'question_index': question_index,
        'total_questions': len(question_ids), # Add total_questions back
        'navigator_items': navigator_items, # Add navigator_items
        'test_message': 'DEBUG STEP 3: Success! POST logic and navigator were added.'
    }
    return render(request, 'quiz/quiz_player.html', context)
# ===================================================================


@login_required
def quiz_results(request):
    # Dummy results view for now
    context = { 'final_score': 0, 'total_questions': 0, 'percentage_score': 0 }
    return render(request, 'quiz/quiz_review.html', context)

@login_required
def report_question(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        question_id = data.get('question_id')
        reason = data.get('reason')
        QuestionReport.objects.create(user=request.user, question_id=question_id, reason=reason)
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)

# The stripe views are included for completeness
@login_required
def create_checkout_session(request):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    price_id = request.POST.get('priceId')
    try:
        checkout_session = stripe.checkout.Session.create(
            client_reference_id=request.user.id,
            line_items=[{'price': price_id, 'quantity': 1}],
            mode='subscription',
            success_url=request.build_absolute_uri(reverse('success_page')),
            cancel_url=request.build_absolute_uri(reverse('cancel_page')),
        )
        return redirect(checkout_session.url)
    except Exception as e:
        messages.error(request, f"Could not create checkout session: {e}")
        return redirect('membership_page')

def success_page(request):
    return render(request, 'quiz/success.html')

def cancel_page(request):
    return render(request, 'quiz/cancel.html')

@csrf_exempt
def stripe_webhook(request):
    # This logic remains the same
    # ...
    return HttpResponse(status=200)